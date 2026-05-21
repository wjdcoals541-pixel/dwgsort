from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .config import PDF_ROW_CLUSTER_TOLERANCE, PDF_X_TOLERANCE, PDF_Y_TOLERANCE
from .pdf_vector_parser import (
    analyze_pdf_label_rows,
    expand_pdf_region,
    extract_pdf_page_region_text,
    match_pdf_profile_rows,
)


@dataclass
class PdfRegionResult:
    mode: str
    page_start: int
    page_end: int
    default_region: tuple[float, float, float, float] | None
    page_regions: dict[int, tuple[float, float, float, float]]
    pdf_y_tolerance: float
    pdf_x_tolerance: float
    row_cluster_tolerance: float

    def to_settings(self):
        return {
            "mode": self.mode,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "default_region": self.default_region,
            "page_regions": dict(self.page_regions),
            "pdf_y_tolerance": self.pdf_y_tolerance,
            "pdf_x_tolerance": self.pdf_x_tolerance,
            "row_cluster_tolerance": self.row_cluster_tolerance,
        }


class PdfPreviewCanvas(QWidget):
    regionChanged = Signal(tuple)
    inspectRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(720, 520)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self._pixmap = QPixmap()
        self._page_size = (1.0, 1.0)
        self._selection = None
        self._drag_start_page = None
        self._drag_current_page = None
        self._image_rect = QRect()
        self._zoom = 1.0
        self._zoom_mode = "fit_page"
        self._pan = QPoint(0, 0)
        self._panning = False
        self._pan_start = QPoint(0, 0)
        self._pan_origin = QPoint(0, 0)
        self._space_down = False
        self._selection_mode = "drag"
        self._first_click_page = None
        self._hover_page = None
        self._extract_region = None
        self._row_overlays = []
        self._match_overlays = []
        self._show_x_matches = False

    def set_page(self, pixmap, page_width, page_height, selection=None):
        self._pixmap = pixmap
        self._page_size = (float(page_width), float(page_height))
        self._selection = selection
        self._drag_start_page = None
        self._drag_current_page = None
        self.update()

    def clear_selection(self):
        self._selection = None
        self._drag_start_page = None
        self._drag_current_page = None
        self._first_click_page = None
        self._hover_page = None
        self.update()

    def set_selection_mode(self, mode):
        self._selection_mode = mode
        self._drag_start_page = None
        self._drag_current_page = None
        self._first_click_page = None
        self._hover_page = None
        self.update()

    def set_extract_region(self, region):
        self._extract_region = region
        self.update()

    def set_detection_overlay(self, row_overlays=None, match_overlays=None, show_x_matches=False):
        self._row_overlays = list(row_overlays or [])
        self._match_overlays = list(match_overlays or [])
        self._show_x_matches = bool(show_x_matches)
        self.update()

    def set_zoom_fit_page(self):
        self._zoom_mode = "fit_page"
        self._pan = QPoint(0, 0)
        self.update()

    def set_zoom_fit_width(self):
        self._zoom_mode = "fit_width"
        self._pan = QPoint(0, 0)
        self.update()

    def set_zoom_percent(self, percent):
        self._zoom_mode = "manual"
        self._zoom = max(0.1, min(8.0, float(percent) / 100.0))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#0f1724"))

        if self._pixmap.isNull():
            painter.setPen(QColor("#dbe7ff"))
            painter.drawText(self.rect(), Qt.AlignCenter, "PDF 페이지를 불러올 수 없습니다.")
            return

        self._image_rect = self._fit_rect(self._pixmap.size())
        painter.drawPixmap(self._image_rect, self._pixmap)

        if self._extract_region is not None:
            extract_rect = self._page_to_widget_rect(self._extract_region).intersected(self._image_rect)
            painter.fillRect(extract_rect, QColor(56, 189, 248, 35))
            painter.setPen(QPen(QColor("#7dd3fc"), 2, Qt.DashLine))
            painter.drawRect(extract_rect)

        for overlay in self._row_overlays:
            self._paint_row_overlay(painter, overlay)

        if self._show_x_matches:
            self._paint_match_overlays(painter)

        rect = None
        if self._drag_start_page is not None and self._drag_current_page is not None:
            rect = self._page_to_widget_rect(self._selection_from_points(self._drag_start_page, self._drag_current_page))
        elif self._first_click_page is not None and self._hover_page is not None:
            rect = self._page_to_widget_rect(self._selection_from_points(self._first_click_page, self._hover_page))
        elif self._selection is not None:
            rect = self._page_to_widget_rect(self._selection)

        if rect is not None:
            rect = rect.intersected(self._image_rect)
            painter.fillRect(rect, QColor(56, 189, 248, 70))
            painter.setPen(QPen(QColor("#38bdf8"), 2, Qt.SolidLine))
            painter.drawRect(rect)

        if self._first_click_page is not None:
            self._paint_first_click_marker(painter)

    def mousePressEvent(self, event):
        self._ensure_image_rect()
        point = event.position().toPoint()
        if event.button() == Qt.RightButton or (event.button() == Qt.LeftButton and self._space_down):
            self._panning = True
            self._pan_start = point
            self._pan_origin = QPoint(self._pan)
            self.setCursor(Qt.ClosedHandCursor)
            return
        if event.button() != Qt.LeftButton or not self._image_rect.contains(point):
            return
        page_point = self._widget_to_page_point(point)
        if self._selection_mode == "two_point":
            if self._first_click_page is None:
                self._first_click_page = page_point
                self._hover_page = page_point
            else:
                selection = self._selection_from_points(self._first_click_page, page_point)
                self._first_click_page = None
                self._hover_page = None
                self._selection = selection
                self.regionChanged.emit(self._selection)
            self.setFocus()
            self.update()
            return
        self._drag_start_page = page_point
        self._drag_current_page = page_point
        self.setFocus()
        self.update()

    def mouseMoveEvent(self, event):
        if self._panning:
            delta = event.position().toPoint() - self._pan_start
            self._pan = self._pan_origin + delta
            self.update()
            return
        if self._selection_mode == "two_point" and self._first_click_page is not None:
            self._hover_page = self._widget_to_page_point(event.position().toPoint())
            self.update()
            return
        if self._drag_start_page is None:
            return
        self._drag_current_page = self._widget_to_page_point(event.position().toPoint())
        self.update()

    def mouseReleaseEvent(self, event):
        if self._panning and event.button() in (Qt.RightButton, Qt.LeftButton):
            self._panning = False
            self.unsetCursor()
            return
        if event.button() != Qt.LeftButton or self._drag_start_page is None:
            return
        self._drag_current_page = self._widget_to_page_point(event.position().toPoint())
        selection = self._selection_from_points(self._drag_start_page, self._drag_current_page)
        widget_rect = self._page_to_widget_rect(selection).intersected(self._image_rect)
        self._drag_start_page = None
        self._drag_current_page = None
        if widget_rect.width() < 4 or widget_rect.height() < 4:
            self.update()
            return
        self._selection = selection
        self.regionChanged.emit(self._selection)
        self.update()

    def wheelEvent(self, event):
        if self._pixmap.isNull():
            return
        delta = event.angleDelta().y()
        if delta == 0:
            return
        factor = 1.15 if delta > 0 else 1 / 1.15
        self._zoom = max(0.1, min(8.0, self._current_scale() * factor))
        self._zoom_mode = "manual"
        event.accept()
        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and self._first_click_page is not None:
            self._first_click_page = None
            self._hover_page = None
            event.accept()
            self.update()
            return

        if event.key() == Qt.Key_Space:
            self._space_down = True
            self.setCursor(Qt.OpenHandCursor)
            event.accept()
            return

        if self._selection is None:
            super().keyPressEvent(event)
            return

        key = event.key()
        if key not in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            super().keyPressEvent(event)
            return

        step_px = 10 if event.modifiers() & Qt.ShiftModifier else 1
        dx_page, dy_page = self._page_delta_for_pixels(step_px)
        dx = 0.0
        dy = 0.0
        if key == Qt.Key_Left:
            dx = -dx_page
        elif key == Qt.Key_Right:
            dx = dx_page
        elif key == Qt.Key_Up:
            dy = -dy_page
        elif key == Qt.Key_Down:
            dy = dy_page

        if event.modifiers() & Qt.ControlModifier:
            self._selection = self._resize_selection(dx, dy)
        else:
            self._selection = self._move_selection(dx, dy)
        self.regionChanged.emit(self._selection)
        self.inspectRequested.emit()
        event.accept()
        self.update()

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Space:
            self._space_down = False
            if not self._panning:
                self.unsetCursor()
            event.accept()
            return
        super().keyReleaseEvent(event)

    def _fit_rect(self, size):
        margin = 12
        available = self.rect().adjusted(margin, margin, -margin, -margin)
        if available.width() <= 0 or available.height() <= 0:
            return QRect()
        if self._zoom_mode == "fit_width":
            scale = available.width() / size.width()
        elif self._zoom_mode == "manual":
            scale = self._zoom
        else:
            scale = min(available.width() / size.width(), available.height() / size.height())
        width = int(size.width() * scale)
        height = int(size.height() * scale)
        x = available.x() + (available.width() - width) // 2 + self._pan.x()
        y = available.y() + (available.height() - height) // 2 + self._pan.y()
        return QRect(x, y, width, height)

    def _current_scale(self):
        if self._pixmap.isNull():
            return 1.0
        margin = 12
        available = self.rect().adjusted(margin, margin, -margin, -margin)
        if self._zoom_mode == "fit_width":
            return available.width() / max(1, self._pixmap.width())
        if self._zoom_mode == "manual":
            return self._zoom
        return min(
            available.width() / max(1, self._pixmap.width()),
            available.height() / max(1, self._pixmap.height()),
        )

    def _clamp_point(self, point):
        x = min(max(point.x(), self._image_rect.left()), self._image_rect.right())
        y = min(max(point.y(), self._image_rect.top()), self._image_rect.bottom())
        return QPoint(x, y)

    def _ensure_image_rect(self):
        if not self._pixmap.isNull():
            self._image_rect = self._fit_rect(self._pixmap.size())

    def _widget_to_page_point(self, point):
        self._ensure_image_rect()
        point = self._clamp_point(point)
        page_width, page_height = self._page_size
        sx = page_width / max(1, self._image_rect.width())
        sy = page_height / max(1, self._image_rect.height())
        x = (point.x() - self._image_rect.left()) * sx
        y = (point.y() - self._image_rect.top()) * sy
        x = min(max(x, 0.0), page_width)
        y = min(max(y, 0.0), page_height)
        return round(x, 2), round(y, 2)

    def _selection_from_points(self, first, second):
        x0, y0 = first
        x1, y1 = second
        return tuple(round(v, 2) for v in (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))

    def _page_delta_for_pixels(self, pixels):
        self._ensure_image_rect()
        page_width, page_height = self._page_size
        return (
            page_width / max(1, self._image_rect.width()) * pixels,
            page_height / max(1, self._image_rect.height()) * pixels,
        )

    def _move_selection(self, dx, dy):
        page_width, page_height = self._page_size
        x0, y0, x1, y1 = self._selection
        width = x1 - x0
        height = y1 - y0
        nx0 = min(max(0.0, x0 + dx), max(0.0, page_width - width))
        ny0 = min(max(0.0, y0 + dy), max(0.0, page_height - height))
        return tuple(round(v, 2) for v in (nx0, ny0, nx0 + width, ny0 + height))

    def _resize_selection(self, dx, dy):
        page_width, page_height = self._page_size
        x0, y0, x1, y1 = self._selection
        nx1 = min(max(x0 + 1.0, x1 + dx), page_width)
        ny1 = min(max(y0 + 1.0, y1 + dy), page_height)
        return tuple(round(v, 2) for v in (x0, y0, nx1, ny1))

    def _paint_row_overlay(self, painter, overlay):
        y = overlay.get("y")
        if y is None:
            return
        height = max(float(overlay.get("height", 2.0)), 2.5)
        role = overlay.get("role", "excluded")
        colors = {
            "distance": QColor(250, 204, 21, 85),
            "elevation": QColor(34, 197, 94, 85),
            "excluded": QColor(148, 163, 184, 55),
            "warning": QColor(248, 113, 113, 65),
            "label": QColor(59, 130, 246, 35),
        }
        color = colors.get(role, colors["excluded"])
        page_width, _page_height = self._page_size
        rect = self._page_to_widget_rect((0, y - height / 2, page_width, y + height / 2))
        rect = rect.intersected(self._image_rect)
        painter.fillRect(rect, color)
        painter.setPen(QPen(QColor(color.red(), color.green(), color.blue(), 160), 1))
        painter.drawLine(rect.left(), rect.center().y(), rect.right(), rect.center().y())

    def _paint_match_overlays(self, painter):
        for overlay in self._match_overlays[:300]:
            try:
                x0 = float(overlay["distance_x"])
                y0 = float(overlay["distance_y"])
                x1 = float(overlay["elevation_x"])
                y1 = float(overlay["elevation_y"])
            except (TypeError, ValueError, KeyError):
                continue
            p0 = self._page_to_widget_point((x0, y0))
            p1 = self._page_to_widget_point((x1, y1))
            ok = overlay.get("ok", False)
            painter.setPen(QPen(QColor("#22c55e" if ok else "#ef4444"), 1))
            painter.drawLine(p0, p1)

    def _paint_first_click_marker(self, painter):
        point = self._page_to_widget_point(self._first_click_page)
        painter.setPen(QPen(QColor("#facc15"), 2))
        painter.drawLine(point.x() - 7, point.y(), point.x() + 7, point.y())
        painter.drawLine(point.x(), point.y() - 7, point.x(), point.y() + 7)

    def _page_to_widget_rect(self, selection):
        page_width, page_height = self._page_size
        sx = self._image_rect.width() / max(1.0, page_width)
        sy = self._image_rect.height() / max(1.0, page_height)
        x0, y0, x1, y1 = selection
        left = int(self._image_rect.left() + x0 * sx)
        top = int(self._image_rect.top() + y0 * sy)
        right = int(self._image_rect.left() + x1 * sx)
        bottom = int(self._image_rect.top() + y1 * sy)
        return QRect(QPoint(left, top), QPoint(right, bottom)).normalized()

    def _page_to_widget_point(self, point):
        page_width, page_height = self._page_size
        sx = self._image_rect.width() / max(1.0, page_width)
        sy = self._image_rect.height() / max(1.0, page_height)
        x, y = point
        return QPoint(
            int(self._image_rect.left() + x * sx),
            int(self._image_rect.top() + y * sy),
        )


class PdfRegionDialog(QDialog):
    MODE_ALL = "all_pages"
    MODE_PER_PAGE = "per_page"

    def __init__(self, pdf_path, page_start=1, page_end=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PDF 영역 지정")
        self.resize(980, 720)
        self.pdf_path = pdf_path
        self.result = None
        self._regions = {}

        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("PDF 미리보기에는 PyMuPDF(fitz)가 필요합니다.") from exc

        self._fitz = fitz
        self._doc = fitz.open(pdf_path)
        self._page_start = max(1, int(page_start or 1))
        requested_end = int(page_end) if page_end else self._doc.page_count
        self._page_end = min(self._doc.page_count, max(self._page_start, requested_end))
        self._pages = list(range(self._page_start, self._page_end + 1))
        self._page_index = 0
        self._render_scale = 1.6
        self._last_inspection = None

        self._build_ui()
        self._render_current_page()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        top = QHBoxLayout()
        self.page_label = QLabel("")
        self.coord_label = QLabel("좌표: -")
        self.coord_label.setObjectName("Muted")
        top.addWidget(self.page_label)
        top.addStretch(1)
        top.addWidget(self.coord_label)
        layout.addLayout(top)

        self.canvas = PdfPreviewCanvas()
        self.canvas.regionChanged.connect(self._store_region)
        self.canvas.inspectRequested.connect(self._inspect_current_region)
        layout.addWidget(self.canvas, 1)

        mode_controls = QHBoxLayout()
        mode_controls.setContentsMargins(0, 0, 0, 0)
        self.drag_select_button = QPushButton("드래그 선택")
        self.two_point_button = QPushButton("두 점 선택")
        self.drag_select_button.setCheckable(True)
        self.two_point_button.setCheckable(True)
        self.drag_select_button.setChecked(True)
        self.selection_mode_group = QButtonGroup(self)
        self.selection_mode_group.addButton(self.drag_select_button)
        self.selection_mode_group.addButton(self.two_point_button)
        self.drag_select_button.clicked.connect(lambda: self.canvas.set_selection_mode("drag"))
        self.two_point_button.clicked.connect(lambda: self.canvas.set_selection_mode("two_point"))
        mode_controls.addWidget(self.drag_select_button)
        mode_controls.addWidget(self.two_point_button)
        mode_controls.addStretch(1)
        layout.addLayout(mode_controls)

        zoom_controls = QHBoxLayout()
        zoom_controls.setContentsMargins(0, 0, 0, 0)
        for text, handler in [
            ("전체 보기", lambda: self.canvas.set_zoom_fit_page()),
            ("가로폭 맞춤", lambda: self.canvas.set_zoom_fit_width()),
            ("100%", lambda: self._set_render_scale(1.0)),
            ("200%", lambda: self._set_render_scale(2.0)),
            ("400%", lambda: self._set_render_scale(4.0)),
            ("800%", lambda: self._set_render_scale(8.0)),
        ]:
            button = QPushButton(text)
            button.clicked.connect(handler)
            zoom_controls.addWidget(button)
        zoom_controls.addStretch(1)
        layout.addLayout(zoom_controls)

        pdf_settings = QHBoxLayout()
        pdf_settings.setContentsMargins(0, 0, 0, 0)
        self.pdf_y_spin = self._make_pdf_spin(PDF_Y_TOLERANCE)
        self.pdf_x_spin = self._make_pdf_spin(PDF_X_TOLERANCE)
        self.pdf_row_spin = self._make_pdf_spin(PDF_ROW_CLUSTER_TOLERANCE)
        for label, widget in [
            ("PDF Y오차", self.pdf_y_spin),
            ("PDF X오차", self.pdf_x_spin),
            ("PDF 행분리", self.pdf_row_spin),
        ]:
            pdf_settings.addWidget(QLabel(label))
            pdf_settings.addWidget(widget)
        self.show_x_matches_check = QCheckBox("X매칭 보기")
        self.show_x_matches_check.stateChanged.connect(lambda _state: self._refresh_x_match_overlay())
        pdf_settings.addWidget(self.show_x_matches_check)
        pdf_settings.addStretch(1)
        layout.addLayout(pdf_settings)

        self.pdf_y_spin.valueChanged.connect(lambda _value: self._inspect_current_region(silent=True))
        self.pdf_x_spin.valueChanged.connect(lambda _value: self._inspect_current_region(silent=True))
        self.pdf_row_spin.valueChanged.connect(lambda _value: self._inspect_current_region(silent=True))

        self.inspect_label = QLabel("영역 검사: -")
        self.inspect_label.setWordWrap(True)
        self.inspect_label.setObjectName("Muted")
        layout.addWidget(self.inspect_label)

        self.legend_label = QLabel(
            "표시 설명: 파란 실선=직접 선택한 영역 / 하늘색 점선=실제 추출 영역(자동 확장 포함) / "
            "노란 띠=누가거리 행 / 초록 띠=관저고 행 / 회색 띠=제외된 후보 행 / "
            "옅은 파란 띠=라벨 기준 PDF Y오차 범위. 실제 추출 영역은 선택 영역의 약 15%만큼 확장됩니다."
        )
        self.legend_label.setWordWrap(True)
        self.legend_label.setObjectName("Muted")
        layout.addWidget(self.legend_label)

        controls = QHBoxLayout()
        self.prev_button = QPushButton("이전 페이지")
        self.next_button = QPushButton("다음 페이지")
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("모든 페이지 동일 좌표 적용", self.MODE_ALL)
        self.mode_combo.addItem("페이지별 개별 좌표 적용", self.MODE_PER_PAGE)
        self.apply_all_button = QPushButton("현재 좌표를 전체 페이지에 적용")
        self.inspect_button = QPushButton("영역 검사")
        self.reset_button = QPushButton("영역 다시 선택")
        self.ok_button = QPushButton("적용")
        self.cancel_button = QPushButton("취소")

        self.prev_button.clicked.connect(self._previous_page)
        self.next_button.clicked.connect(self._next_page)
        self.mode_combo.currentIndexChanged.connect(self._render_current_page)
        self.apply_all_button.clicked.connect(self._apply_current_region_to_all)
        self.inspect_button.clicked.connect(self._inspect_current_region)
        self.reset_button.clicked.connect(self._reset_current_region)
        self.ok_button.clicked.connect(self._accept_region)
        self.cancel_button.clicked.connect(self.reject)

        controls.addWidget(self.prev_button)
        controls.addWidget(self.next_button)
        controls.addWidget(self.mode_combo, 1)
        controls.addWidget(self.apply_all_button)
        controls.addWidget(self.inspect_button)
        controls.addWidget(self.reset_button)
        controls.addWidget(self.ok_button)
        controls.addWidget(self.cancel_button)
        layout.addLayout(controls)

    def _make_pdf_spin(self, value):
        spin = QDoubleSpinBox()
        spin.setRange(0.1, 1000.0)
        spin.setDecimals(2)
        spin.setSingleStep(0.5)
        spin.setValue(value)
        spin.setFixedWidth(82)
        return spin

    def _render_current_page(self):
        page_number = self._pages[self._page_index]
        page = self._doc.load_page(page_number - 1)
        matrix = self._fitz.Matrix(self._render_scale, self._render_scale)
        try:
            pix = page.get_pixmap(matrix=matrix, alpha=False)
        except Exception as exc:
            if self._render_scale > 4.0:
                self._render_scale = 4.0
                QMessageBox.warning(self, "확대 렌더링 실패", f"요청한 배율이 너무 큽니다.\n400%로 다시 표시합니다.\n\n{exc}")
                self._render_current_page()
                return
            raise
        image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
        pixmap = QPixmap.fromImage(image)
        region = self._region_for_page(page_number)
        self.canvas.set_page(pixmap, page.rect.width, page.rect.height, region)
        self._update_extract_region_overlay(region)
        self.page_label.setText(f"페이지 {page_number} / {self._doc.page_count}  (처리 범위 {self._page_start} ~ {self._page_end})")
        self.prev_button.setEnabled(self._page_index > 0)
        self.next_button.setEnabled(self._page_index < len(self._pages) - 1)
        self._update_coord_label(region)

    def _set_render_scale(self, scale):
        self._render_scale = max(0.5, min(8.0, float(scale)))
        self.canvas.set_zoom_percent(100)
        self._render_current_page()

    def _previous_page(self):
        if self._page_index > 0:
            self._page_index -= 1
            self._render_current_page()

    def _next_page(self):
        if self._page_index < len(self._pages) - 1:
            self._page_index += 1
            self._render_current_page()

    def _current_page_number(self):
        return self._pages[self._page_index]

    def _current_mode(self):
        return self.mode_combo.currentData()

    def _region_for_page(self, page_number):
        if self._current_mode() == self.MODE_ALL:
            return self._regions.get("all")
        return self._regions.get(page_number)

    def _store_region(self, region):
        page_number = self._current_page_number()
        if self._current_mode() == self.MODE_ALL:
            self._regions["all"] = region
        else:
            self._regions[page_number] = region
        self._update_coord_label(region)
        self._update_extract_region_overlay(region)
        self._inspect_current_region()

    def _apply_current_region_to_all(self):
        page_number = self._current_page_number()
        region = self._region_for_page(page_number)
        if region is None:
            QMessageBox.warning(self, "영역 필요", "먼저 현재 페이지에서 영역을 드래그해 선택하세요.")
            return
        self._regions["all"] = region
        self.mode_combo.setCurrentIndex(0)
        self._render_current_page()

    def _reset_current_region(self):
        page_number = self._current_page_number()
        if self._current_mode() == self.MODE_ALL:
            self._regions.pop("all", None)
        else:
            self._regions.pop(page_number, None)
        self.canvas.clear_selection()
        self.canvas.set_extract_region(None)
        self.canvas.set_detection_overlay()
        self._update_coord_label(None)
        self.inspect_label.setText("영역 검사: -")
        self._last_inspection = None

    def _update_extract_region_overlay(self, region):
        if region is None:
            self.canvas.set_extract_region(None)
            return
        page = self._doc.load_page(self._current_page_number() - 1)
        self.canvas.set_extract_region(expand_pdf_region(region, page.rect.width, page.rect.height))

    def _inspect_current_region(self, silent=False):
        page_number = self._current_page_number()
        region = self._region_for_page(page_number)
        if region is None:
            if not silent:
                QMessageBox.warning(self, "영역 필요", "먼저 현재 페이지에서 영역을 드래그해 선택하세요.")
            return

        logs = []
        try:
            _df, items, _expanded = extract_pdf_page_region_text(
                self.pdf_path,
                page_number,
                region,
                logs.append,
            )
            rows = analyze_pdf_label_rows(
                items,
                logs.append,
                pdf_y_tolerance=self.pdf_y_spin.value(),
                pdf_x_tolerance=self.pdf_x_spin.value(),
                row_cluster_tolerance=self.pdf_row_spin.value(),
            )
            matched_df = match_pdf_profile_rows(rows, logs.append, pdf_x_tolerance=self.pdf_x_spin.value())
        except Exception as exc:
            self.inspect_label.setText(f"영역 검사: 오류 - {exc}")
            QMessageBox.warning(self, "영역 검사 오류", str(exc))
            return

        page_rows = rows.get(page_number, {})
        distance_found = page_rows.get("distance_label") is not None
        elevation_found = page_rows.get("elevation_label") is not None
        distance_count = len(page_rows.get("distance_numbers") or [])
        elevation_count = len(page_rows.get("elevation_numbers") or [])
        match_count = int((matched_df["상태"] == "정상").sum()) if not matched_df.empty else 0
        fail_count = int(len(matched_df) - match_count) if not matched_df.empty else 0
        line_count = int(matched_df["line_id"].nunique()) if not matched_df.empty and "line_id" in matched_df.columns else 0
        selected_row_count = int(page_rows.get("selected_distance_row_y") is not None) + int(page_rows.get("selected_elevation_row_y") is not None)
        excluded_count = max(0, len(page_rows.get("number_rows") or []) - selected_row_count)

        if distance_found and elevation_found and distance_count and elevation_count:
            status = "검사 가능"
        else:
            status = "라벨 또는 숫자가 부족합니다"

        self.inspect_label.setText(
            "영역 검사: "
            f"누가거리 라벨={'찾음' if distance_found else '못 찾음'}"
            f"{' / ' + page_rows['distance_label']['contents'] if distance_found else ''}\n"
            f"관저고 라벨={'찾음' if elevation_found else '못 찾음'}"
            f"{' / ' + page_rows['elevation_label']['contents'] if elevation_found else ''}\n"
            f"누가거리 선택 행: y={page_rows.get('selected_distance_row_y')}, {distance_count}개 / "
            f"관저고 선택 행: y={page_rows.get('selected_elevation_row_y')}, {elevation_count}개\n"
            f"제외 행: {max(0, excluded_count)}개 / "
            f"예상 매칭: 성공 {match_count}개 / 실패 {fail_count}개 / "
            f"라인 분리: {line_count}개 / 상태={status}"
        )
        self._last_inspection = {
            "rows": rows,
            "matched_df": matched_df,
            "page_rows": page_rows,
        }
        self.canvas.set_detection_overlay(
            self._build_row_overlays(page_rows),
            self._build_match_overlays(page_rows, matched_df),
            self.show_x_matches_check.isChecked(),
        )

    def _refresh_x_match_overlay(self):
        if not self._last_inspection:
            return
        self.canvas.set_detection_overlay(
            self._build_row_overlays(self._last_inspection["page_rows"]),
            self._build_match_overlays(self._last_inspection["page_rows"], self._last_inspection["matched_df"]),
            self.show_x_matches_check.isChecked(),
        )

    def _build_row_overlays(self, page_rows):
        overlays = []
        selected_distance_y = page_rows.get("selected_distance_row_y")
        selected_elevation_y = page_rows.get("selected_elevation_row_y")
        for label_key in ("distance_label", "elevation_label"):
            label = page_rows.get(label_key)
            if label:
                overlays.append({"y": label["y"], "height": self.pdf_y_spin.value() * 2, "role": "label"})
        for row in page_rows.get("number_rows") or []:
            role = "excluded"
            if selected_distance_y is not None and abs(row["y"] - selected_distance_y) < 0.01:
                role = "distance"
            elif selected_elevation_y is not None and abs(row["y"] - selected_elevation_y) < 0.01:
                role = "elevation"
            overlays.append({"y": row["y"], "height": max(self.pdf_row_spin.value() * 2, 3.0), "role": role})
        return overlays

    def _build_match_overlays(self, page_rows, matched_df):
        distance_by_text_x = {
            (item["contents"], f"{float(item['x']):.2f}"): item
            for item in page_rows.get("distance_numbers") or []
        }
        elevation_by_text_x = {
            (item["contents"], f"{float(item['x']):.2f}"): item
            for item in page_rows.get("elevation_numbers") or []
        }
        overlays = []
        if matched_df is None or matched_df.empty:
            return overlays
        for _, row in matched_df.head(300).iterrows():
            distance = distance_by_text_x.get((str(row.get("원본 누가거리")), str(row.get("누가거리 X"))))
            elevation = elevation_by_text_x.get((str(row.get("원본 관저고")), str(row.get("관저고 X"))))
            if not distance or not elevation:
                continue
            overlays.append(
                {
                    "distance_x": distance["x"],
                    "distance_y": distance["y"],
                    "elevation_x": elevation["x"],
                    "elevation_y": elevation["y"],
                    "ok": row.get("상태") == "정상",
                }
            )
        return overlays

    def _accept_region(self):
        mode = self._current_mode()
        if mode == self.MODE_ALL:
            region = self._regions.get("all")
            if region is None:
                QMessageBox.warning(self, "영역 필요", "PDF 데이터 영역을 먼저 지정하세요.")
                return
            page_regions = {page: region for page in self._pages}
            default_region = region
        else:
            missing = [page for page in self._pages if page not in self._regions]
            if missing:
                QMessageBox.warning(
                    self,
                    "페이지별 좌표 필요",
                    f"{missing[0]}페이지에 PDF 데이터 영역이 지정되지 않았습니다.\n"
                    "페이지별 개별 좌표 적용 모드에서는 모든 처리 대상 페이지에 좌표가 필요합니다.",
                )
                return
            page_regions = {page: self._regions[page] for page in self._pages}
            default_region = None

        self.result = PdfRegionResult(
            mode=mode,
            page_start=self._page_start,
            page_end=self._page_end,
            default_region=default_region,
            page_regions=page_regions,
            pdf_y_tolerance=self.pdf_y_spin.value(),
            pdf_x_tolerance=self.pdf_x_spin.value(),
            row_cluster_tolerance=self.pdf_row_spin.value(),
        )
        self.accept()

    def _update_coord_label(self, region):
        if region is None:
            self.coord_label.setText("좌표: -")
            return
        x0, y0, x1, y1 = region
        self.coord_label.setText(f"좌표: x0={x0:.2f}, y0={y0:.2f}, x1={x1:.2f}, y1={y1:.2f}")

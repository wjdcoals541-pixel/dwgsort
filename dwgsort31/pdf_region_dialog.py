from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


@dataclass
class PdfRegionResult:
    mode: str
    page_start: int
    page_end: int
    default_region: tuple[float, float, float, float] | None
    page_regions: dict[int, tuple[float, float, float, float]]

    def to_settings(self):
        return {
            "mode": self.mode,
            "page_start": self.page_start,
            "page_end": self.page_end,
            "default_region": self.default_region,
            "page_regions": dict(self.page_regions),
        }


class PdfPreviewCanvas(QWidget):
    regionChanged = Signal(tuple)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(720, 520)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._pixmap = QPixmap()
        self._page_size = (1.0, 1.0)
        self._selection = None
        self._drag_start_page = None
        self._drag_current_page = None
        self._image_rect = QRect()
        self._zoom = 1.0

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

        rect = None
        if self._drag_start_page is not None and self._drag_current_page is not None:
            rect = self._page_to_widget_rect(self._selection_from_points(self._drag_start_page, self._drag_current_page))
        elif self._selection is not None:
            rect = self._page_to_widget_rect(self._selection)

        if rect is not None:
            rect = rect.intersected(self._image_rect)
            painter.fillRect(rect, QColor(56, 189, 248, 70))
            painter.setPen(QPen(QColor("#38bdf8"), 2, Qt.SolidLine))
            painter.drawRect(rect)

    def mousePressEvent(self, event):
        self._ensure_image_rect()
        if event.button() != Qt.LeftButton or not self._image_rect.contains(event.position().toPoint()):
            return
        page_point = self._widget_to_page_point(event.position().toPoint())
        self._drag_start_page = page_point
        self._drag_current_page = page_point
        self.update()

    def mouseMoveEvent(self, event):
        if self._drag_start_page is None:
            return
        self._drag_current_page = self._widget_to_page_point(event.position().toPoint())
        self.update()

    def mouseReleaseEvent(self, event):
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
        self._zoom = max(0.5, min(5.0, self._zoom * factor))
        event.accept()
        self.update()

    def _fit_rect(self, size):
        margin = 12
        available = self.rect().adjusted(margin, margin, -margin, -margin)
        if available.width() <= 0 or available.height() <= 0:
            return QRect()
        scale = min(available.width() / size.width(), available.height() / size.height()) * self._zoom
        width = int(size.width() * scale)
        height = int(size.height() * scale)
        x = available.x() + (available.width() - width) // 2
        y = available.y() + (available.height() - height) // 2
        return QRect(x, y, width, height)

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
        layout.addWidget(self.canvas, 1)

        controls = QHBoxLayout()
        self.prev_button = QPushButton("이전 페이지")
        self.next_button = QPushButton("다음 페이지")
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("모든 페이지 동일 좌표 적용", self.MODE_ALL)
        self.mode_combo.addItem("페이지별 개별 좌표 적용", self.MODE_PER_PAGE)
        self.apply_all_button = QPushButton("현재 좌표를 전체 페이지에 적용")
        self.reset_button = QPushButton("영역 다시 선택")
        self.ok_button = QPushButton("적용")
        self.cancel_button = QPushButton("취소")

        self.prev_button.clicked.connect(self._previous_page)
        self.next_button.clicked.connect(self._next_page)
        self.mode_combo.currentIndexChanged.connect(self._render_current_page)
        self.apply_all_button.clicked.connect(self._apply_current_region_to_all)
        self.reset_button.clicked.connect(self._reset_current_region)
        self.ok_button.clicked.connect(self._accept_region)
        self.cancel_button.clicked.connect(self.reject)

        controls.addWidget(self.prev_button)
        controls.addWidget(self.next_button)
        controls.addWidget(self.mode_combo, 1)
        controls.addWidget(self.apply_all_button)
        controls.addWidget(self.reset_button)
        controls.addWidget(self.ok_button)
        controls.addWidget(self.cancel_button)
        layout.addLayout(controls)

    def _render_current_page(self):
        page_number = self._pages[self._page_index]
        page = self._doc.load_page(page_number - 1)
        matrix = self._fitz.Matrix(1.6, 1.6)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        image = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888).copy()
        pixmap = QPixmap.fromImage(image)
        region = self._region_for_page(page_number)
        self.canvas.set_page(pixmap, page.rect.width, page.rect.height, region)
        self.page_label.setText(f"페이지 {page_number} / {self._doc.page_count}  (처리 범위 {self._page_start} ~ {self._page_end})")
        self.prev_button.setEnabled(self._page_index > 0)
        self.next_button.setEnabled(self._page_index < len(self._pages) - 1)
        self._update_coord_label(region)

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
        self._update_coord_label(None)

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
        )
        self.accept()

    def _update_coord_label(self, region):
        if region is None:
            self.coord_label.setText("좌표: -")
            return
        x0, y0, x1, y1 = region
        self.coord_label.setText(f"좌표: x0={x0:.2f}, y0={y0:.2f}, x1={x1:.2f}, y1={y1:.2f}")

import os
import sys
import time
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QThread
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizeGrip,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties

from .config import (
    DEFAULT_MAX_DISTANCE,
    DEFAULT_PEAK_PROMINENCE,
    DEFAULT_SLOPE_CHANGE,
    DEFAULT_TOLERANCE,
    SAVE_MODE_COMPAT_24,
    SAVE_MODE_COMPAT_33,
    SAVE_MODE_EXTENDED_31,
    SUPPORTED_EXTENSIONS,
)
from .excel_compat import add_result_column, filter_graph_points_24, process_excel_data
from .excel_compat33 import filter_graph_points_33
from .pdf_region_dialog import PdfRegionDialog
from .pdf_vector_parser import analyze_pdf_label_rows, extract_pdf_region_text, match_pdf_profile_rows
from .pdf_point_filter import filter_pdf_graph_points
from .qt_styles import apply_fluent_theme
from .qt_widgets import Card, DropZone, MetricCard, make_button
from .qt_workers import AnalysisWorker
from .utils import safe_output_path


KOREAN_FONT = None
if sys.platform.startswith("win"):
    font_path = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts" / "malgun.ttf"
    if font_path.exists():
        KOREAN_FONT = FontProperties(fname=str(font_path))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setWindowTitle("CAD PDF Converter Pro - DWG Sort 3.3")
        self.resize(1280, 820)
        self.setMinimumSize(600, 500)
        self.selected_files = []
        self.worker = None
        self.thread = None
        self.last_filtered_df = None
        self.last_saved_path = None
        self.pdf_region_config = None
        self.pdf_region_text_df = None
        self.pdf_region_text_items = []
        self.pdf_label_rows = {}
        self.pdf_profile_match_df = None
        self.preview_has_plot = False
        self._compact_mode = None

        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.title_bar = TitleBar(self)
        outer.addWidget(self.title_bar)

        content = QWidget()
        shell = QHBoxLayout(content)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)

        shell.addWidget(self._build_main(), 1)
        outer.addWidget(content, 1)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.addPermanentWidget(QSizeGrip(self), 0)
        self.set_status("")
        self._set_working(False)
        self.apply_responsive_layout()

    def _build_main(self):
        page = QWidget()
        self.main_layout = QVBoxLayout(page)
        layout = self.main_layout
        layout.setContentsMargins(16, 12, 16, 8)
        layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(6)

        # Left panel with scroll
        left_page = QWidget()
        self.left_layout = QVBoxLayout(left_page)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(10)
        self.left_layout.addWidget(self._build_file_card(), 0)
        self.left_layout.addWidget(self._build_graph_preview_card(), 2)
        self.left_layout.addStretch(0)

        left_scroll = QScrollArea()
        left_scroll.setWidget(left_page)
        left_scroll.setWidgetResizable(True)
        left_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { width: 8px; margin: 0; background: transparent; }
            QScrollBar::handle:vertical { background: #888; border-radius: 4px; min-height: 20px; }
            QScrollBar::handle:vertical:hover { background: #aaa; }
        """)

        # Right panel with scroll
        right_page = QWidget()
        self.right_layout = QVBoxLayout(right_page)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(10)
        self.right_layout.addWidget(self._build_result_card(), 2)
        self.right_layout.addWidget(self._build_settings_card(), 0)
        self.right_layout.addWidget(self._build_run_card(), 0)
        self.right_layout.addWidget(self._build_log_card(), 1)
        self.right_layout.addWidget(self._build_progress_card(), 0)
        self.right_layout.addStretch(0)

        right_scroll = QScrollArea()
        right_scroll.setWidget(right_page)
        right_scroll.setWidgetResizable(True)
        right_scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { width: 8px; margin: 0; background: transparent; }
            QScrollBar::handle:vertical { background: #888; border-radius: 4px; min-height: 20px; }
            QScrollBar::handle:vertical:hover { background: #aaa; }
        """)

        self.splitter.addWidget(left_scroll)
        self.splitter.addWidget(right_scroll)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        layout.addWidget(self.splitter, 1)
        
        self.left_scroll = left_scroll
        self.right_scroll = right_scroll
        return page

    def _build_file_card(self):
        card = Card("파일 선택")
        self.file_card = card
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.drop_zone = DropZone()
        self.drop_zone.setMinimumHeight(40)
        self.drop_zone.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.drop_zone.filesDropped.connect(self.add_files)
        self.drop_zone.chooseClicked.connect(self.choose_files)
        self.drop_zone.pdfRegionClicked.connect(self.open_pdf_region_dialog)
        card.layout.addWidget(self.drop_zone, 0)

        self.file_list = QListWidget()
        self.file_list.setMinimumHeight(30)
        self.file_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.file_list.currentItemChanged.connect(lambda _current, _previous: self.update_inline_preview())
        card.layout.addWidget(self.file_list, 1)

        file_actions = QHBoxLayout()
        self.add_file_button = make_button("파일 추가")
        self.remove_file_button = make_button("선택 제거")
        self.clear_file_button = make_button("전체 비우기")
        self.add_file_button.clicked.connect(self.choose_files)
        self.remove_file_button.clicked.connect(self.remove_selected_files)
        self.clear_file_button.clicked.connect(self.clear_files)
        file_actions.addWidget(self.add_file_button)
        file_actions.addWidget(self.remove_file_button)
        file_actions.addWidget(self.clear_file_button)
        card.layout.addLayout(file_actions, 0)
        return card

    def _build_settings_card(self):
        card = Card("변환 설정")
        self.settings_card = card
        grid = QGridLayout()
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(6)

        self.save_combo = QComboBox()
        self.save_combo.addItems(["2.4", "3.1", "3.3"])
        self.save_combo.setCurrentText("3.3")
        self.save_combo.currentTextChanged.connect(self.update_inline_preview)

        self.tolerance_spin = QDoubleSpinBox()
        self.tolerance_spin.setRange(0.1, 1000.0)
        self.tolerance_spin.setSingleStep(0.5)
        self.tolerance_spin.setValue(DEFAULT_TOLERANCE)
        self.tolerance_spin.valueChanged.connect(self.update_inline_preview)

        self.slope_spin = QDoubleSpinBox()
        self.slope_spin.setRange(0.0, 10.0)
        self.slope_spin.setSingleStep(0.01)
        self.slope_spin.setValue(DEFAULT_SLOPE_CHANGE)
        self.slope_spin.valueChanged.connect(self.update_inline_preview)

        self.max_dist_spin = QDoubleSpinBox()
        self.max_dist_spin.setRange(1.0, 100000.0)
        self.max_dist_spin.setSingleStep(10.0)
        self.max_dist_spin.setValue(DEFAULT_MAX_DISTANCE)
        self.max_dist_spin.valueChanged.connect(self.update_inline_preview)

        self.peak_prominence_spin = QDoubleSpinBox()
        self.peak_prominence_spin.setRange(0.0, 10.0)
        self.peak_prominence_spin.setSingleStep(0.05)
        self.peak_prominence_spin.setValue(DEFAULT_PEAK_PROMINENCE)
        self.peak_prominence_spin.valueChanged.connect(self.update_inline_preview)

        self.pdf_start_spin = QSpinBox()
        self.pdf_start_spin.setRange(1, 100000)
        self.pdf_start_spin.setValue(1)
        self.pdf_end_spin = QSpinBox()
        self.pdf_end_spin.setRange(0, 100000)
        self.pdf_end_spin.setValue(0)

        for control in [
            self.save_combo,
            self.tolerance_spin,
            self.slope_spin,
            self.max_dist_spin,
            self.peak_prominence_spin,
            self.pdf_start_spin,
            self.pdf_end_spin,
        ]:
            control.setFixedHeight(28)
            control.setMinimumWidth(0)
            control.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

        # Row 1: 저장, Y오차, 기울기
        fields_row1 = [
            ("저장", self.save_combo),
            ("Y오차", self.tolerance_spin),
            ("기울기", self.slope_spin),
        ]
        for idx, (label, widget) in enumerate(fields_row1):
            box = QHBoxLayout()
            box.setContentsMargins(0, 0, 0, 0)
            box.setSpacing(2)
            caption = QLabel(label)
            caption.setObjectName("Muted")
            caption.setFixedWidth(38)
            caption.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            box.addWidget(caption)
            box.addWidget(widget, 1)
            widget.setMinimumWidth(0)
            widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            grid.addLayout(box, 0, idx)
            grid.setColumnStretch(idx, 1)

        # Row 2: 거리, 고점, PDF
        fields_row2 = [
            ("거리", self.max_dist_spin),
            ("고점", self.peak_prominence_spin),
            ("PDF", self._pair_widget(self.pdf_start_spin, self.pdf_end_spin)),
        ]
        for idx, (label, widget) in enumerate(fields_row2):
            box = QHBoxLayout()
            box.setContentsMargins(0, 0, 0, 0)
            box.setSpacing(2)
            caption = QLabel(label)
            caption.setObjectName("Muted")
            caption.setFixedWidth(38)
            caption.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            box.addWidget(caption)
            box.addWidget(widget, 1)
            widget.setMinimumWidth(0)
            widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            grid.addLayout(box, 1, idx)
            grid.setColumnStretch(idx, 1)

        card.layout.addLayout(grid)
        return card

    def _build_graph_preview_card(self):
        card = Card("📊 그래프 미리보기")
        self.graph_preview_card = card
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        self.preview_message = QLabel("미리보기 대기 중")
        self.preview_message.setObjectName("Muted")
        self.preview_message.setWordWrap(True)
        card.layout.addWidget(self.preview_message, 0)

        self.preview_figure = Figure(figsize=(6, 2.7), dpi=100)
        self.preview_canvas = FigureCanvas(self.preview_figure)
        self.preview_canvas.setMinimumHeight(80)
        self.preview_canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        card.layout.addWidget(self.preview_canvas, 1)
        self.clear_preview_plot()
        
        return card

    def _build_run_card(self):
        card = Card("빠른 실행")
        self.run_card = card
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self.run_button = make_button("▷ 변환 시작", primary=True)
        self.reset_button = make_button("↻ 초기화")
        self.excel_button = make_button("엑셀로 저장", success=True)
        self.csv_button = make_button("CSV로 저장")
        self.graph_button = make_button("📈 그래프로 보기")
        self.run_button.clicked.connect(self.start_analysis)
        self.reset_button.clicked.connect(self.reset)
        self.excel_button.clicked.connect(self.export_excel)
        self.csv_button.clicked.connect(self.export_csv)
        self.graph_button.clicked.connect(self.preview_graph)
        for button in [self.run_button, self.reset_button, self.excel_button, self.csv_button, self.graph_button]:
            button.setFixedHeight(34)
            button.setMinimumWidth(60)
        row.addWidget(self.run_button)
        row.addWidget(self.reset_button)
        row.addWidget(self.excel_button)
        row.addWidget(self.csv_button)
        row.addWidget(self.graph_button)
        row.addStretch(1)
        card.layout.addLayout(row)
        return card

    def _build_result_card(self):
        card = Card("변환 결과 미리보기")
        self.result_card = card
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.result_title_label = card.title_label

        stats = QGridLayout()
        stats.setHorizontalSpacing(6)
        stats.setVerticalSpacing(0)
        self.metric_lines = MetricCard("총 라인 수")
        self.metric_pages = MetricCard("총 페이지 수")
        self.metric_quantity = MetricCard("총 수량")
        for metric in [self.metric_lines, self.metric_pages, self.metric_quantity]:
            metric.setMaximumHeight(60)
        stats.addWidget(self.metric_lines, 0, 0)
        stats.addWidget(self.metric_quantity, 0, 1)
        stats.addWidget(self.metric_pages, 0, 2)
        card.layout.addLayout(stats, 0)

        self.table = QTableWidget(0, 3)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.setMinimumHeight(60)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectItems)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setHorizontalHeaderLabels(["관저고", "누가거리", "결과"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setStyleSheet(
            "QHeaderView::section { background: #263244; color: #dbe7ff; border: 0; border-bottom: 1px solid #34465d; padding: 4px; }"
        )
        copy_shortcut = QShortcut(QKeySequence.Copy, self.table)
        copy_shortcut.activated.connect(self.copy_table_selection)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)
        header.addWidget(self.table, 1)
        self.copy_profile_button = make_button("복사")
        self.copy_profile_button.setFixedSize(44, 24)
        self.copy_profile_button.clicked.connect(self.copy_profile_columns)
        header.addWidget(self.copy_profile_button)
        card.layout.addLayout(header, 1)
        return card

    def _build_log_card(self):
        card = Card("실행 로그")
        self.log_card = card
        log_actions = QHBoxLayout()
        log_actions.setContentsMargins(0, 0, 0, 0)
        log_actions.addStretch(1)
        self.copy_log_button = make_button("로그 복사")
        self.copy_log_button.setFixedHeight(24)
        self.copy_log_button.clicked.connect(self.copy_log_to_clipboard)
        log_actions.addWidget(self.copy_log_button)
        card.layout.addLayout(log_actions, 0)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(40)
        self.log_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        card.layout.addWidget(self.log_box, 1)
        return card

    def _build_progress_card(self):
        card = Card("진행 상황")
        self.progress_card = card
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setFixedHeight(24)
        self.percent_label = QLabel("0%")
        self.eta_label = QLabel("예상 남은 시간: -")
        self.eta_label.setObjectName("Muted")
        self.current_label = QLabel("대기 중")
        self.current_label.setObjectName("Muted")
        card.layout.addWidget(self.progress_bar)
        card.layout.addWidget(self.percent_label)
        card.layout.addWidget(self.eta_label)
        card.layout.addWidget(self.current_label)
        return card

    def _pair_widget(self, left, right):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        left.setMinimumWidth(0)
        right.setMinimumWidth(0)
        left.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        right.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        layout.addWidget(left)
        layout.addWidget(right)
        return widget

    def choose_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "도면 파일 선택",
            "",
            "Supported files (*.pdf *.xls *.xlsx);;PDF files (*.pdf);;Excel files (*.xls *.xlsx)",
        )
        self.add_files(files)

    def open_pdf_region_dialog(self):
        file_path = self._current_pdf_file()
        if not file_path:
            self.show_message("PDF 필요", "PDF 영역을 지정할 PDF 파일을 먼저 선택하세요.", error=True)
            return

        try:
            dialog = PdfRegionDialog(
                file_path,
                self.pdf_start_spin.value(),
                self.pdf_end_spin.value() or None,
                self,
            )
        except Exception as exc:
            self.show_message("PDF 미리보기 오류", str(exc), error=True)
            return

        if dialog.exec() == QDialog.Accepted and dialog.result is not None:
            self.pdf_region_config = dialog.result.to_settings()
            self.pdf_region_config["file"] = file_path
            region = self.pdf_region_config.get("default_region")
            if region is None:
                region = self.pdf_region_config["page_regions"].get(self.pdf_region_config["page_start"])
            self.append_log(
                "[PDF] 영역 지정 완료: "
                f"{os.path.basename(file_path)}, "
                f"페이지 {self.pdf_region_config['page_start']}~{self.pdf_region_config['page_end']}, "
                f"x0={region[0]:.2f}, y0={region[1]:.2f}, x1={region[2]:.2f}, y1={region[3]:.2f}"
            )
            self.extract_selected_pdf_region_text(file_path)

    def extract_selected_pdf_region_text(self, file_path):
        if not self.pdf_region_config:
            self.show_message("PDF 영역 필요", "먼저 PDF 영역을 지정하세요.", error=True)
            return

        try:
            df, items = extract_pdf_region_text(file_path, self.pdf_region_config, self.append_log)
        except Exception as exc:
            self.pdf_region_text_df = None
            self.pdf_region_text_items = []
            self.append_log(f"[PDF][ERROR] 선택 영역 텍스트 추출 실패: {exc}")
            self.show_message("PDF 텍스트 추출 오류", str(exc), error=True)
            return

        self.pdf_region_text_df = df
        self.pdf_region_text_items = items
        self.pdf_label_rows = {}
        self.pdf_profile_match_df = None
        if df.empty:
            self.show_message(
                "PDF 텍스트 없음",
                "선택 영역에서 벡터 텍스트를 찾지 못했습니다.\n스캔 PDF이거나 영역이 잘못되었을 수 있습니다.",
                error=True,
            )
            return

        self.append_log("[PDF][DEBUG] Excel 유사 구조 미리보기:")
        for _, row in df.head(30).iterrows():
            self.append_log(
                "[PDF][DEBUG] "
                f"page={row['PDF페이지']}, "
                f"Contents={row['Contents']}, "
                f"Position={row['Position']}, "
                f"bbox={row['BBox']}, "
                f"rotation={row['Rotation']}"
            )
        self.append_log(
            "[PDF] PDF 설정: "
            f"y_tolerance={self.pdf_region_config.get('pdf_y_tolerance', 5.0)}, "
            f"x_tolerance={self.pdf_region_config.get('pdf_x_tolerance', 10.0)}, "
            f"row_cluster_tolerance={self.pdf_region_config.get('row_cluster_tolerance', 1.5)}"
        )
        self.pdf_label_rows = analyze_pdf_label_rows(
            items,
            self.append_log,
            pdf_y_tolerance=self.pdf_region_config.get("pdf_y_tolerance", 5.0),
            pdf_x_tolerance=self.pdf_region_config.get("pdf_x_tolerance", 10.0),
            row_cluster_tolerance=self.pdf_region_config.get("row_cluster_tolerance", 1.5),
        )
        self.pdf_profile_match_df = match_pdf_profile_rows(
            self.pdf_label_rows,
            self.append_log,
            pdf_x_tolerance=self.pdf_region_config.get("pdf_x_tolerance", 10.0),
        )
        if self.pdf_profile_match_df.empty:
            self.last_filtered_df = None
            self.last_saved_path = None
            self.clear_inline_result()
            self.show_message("PDF 결과 없음", "PDF 선택 영역에서 그래프로 표시할 매칭 결과를 만들지 못했습니다.", error=True)
            return

        self.last_filtered_df = filter_pdf_graph_points(
            self.pdf_profile_match_df,
            self.append_log,
            self.slope_spin.value(),
            self.max_dist_spin.value(),
            self.peak_prominence_spin.value(),
        )
        if self.last_filtered_df.empty:
            self.last_filtered_df = None
            self.last_saved_path = None
            self.clear_inline_result()
            self.show_message("PDF 결과 없음", "PDF 선택 영역에서 점 정리 후 결과가 비어 있습니다.", error=True)
            return
        self.last_saved_path = None
        self._populate_table(self.last_filtered_df)
        self.draw_inline_preview(self.last_filtered_df)
        self._update_summary(
            {
                "line_count": 1,
                "page_count": self.pdf_region_config["page_end"] - self.pdf_region_config["page_start"] + 1,
                "quantity_count": int(len(self.last_filtered_df)),
            }
        )
        self.set_preview_message("PDF 추출 결과 미리보기")
        self.set_status("PDF 추출 결과 준비 완료")
        self._set_working(False)

    def _current_pdf_file(self):
        item = self.file_list.currentItem()
        if item and item.text().lower().endswith(".pdf"):
            return item.text()
        return next((path for path in self.selected_files if path.lower().endswith(".pdf")), None)

    def preview_graph(self):
        if not self.selected_files:
            self.show_message("파일 필요", "먼저 Excel 파일을 선택하세요.", error=True)
            return

        file_path = self.file_list.currentItem().text() if self.file_list.currentItem() else self.selected_files[0]
        if file_path.lower().endswith(".pdf"):
            if self.last_filtered_df is None or self.last_filtered_df.empty:
                self.show_message("PDF 결과 필요", "먼저 PDF 영역을 지정해 추출 결과를 만드세요.", error=True)
                return
            try:
                from .plotting import preview_profile

                preview_profile(self.last_filtered_df, f"종단면도 미리보기: {os.path.basename(file_path)}")
                self.set_status("그래프 미리보기 완료")
            except Exception as exc:
                self.append_log(f"미리보기 오류: {exc}")
                self.show_message("미리보기 오류", str(exc), error=True)
                self.set_status("미리보기 오류")
            return

        if not file_path.lower().endswith((".xls", ".xlsx")):
            self.show_message("미리보기 불가", "그래프 미리보기는 Excel 파일만 지원합니다.", error=True)
            return

        try:
            self.set_status("그래프 미리보기 계산 중")
            self.append_log(f"[미리보기] {os.path.basename(file_path)} 계산 중")
            df_result = process_excel_data(file_path, self.append_log, self.tolerance_spin.value())
            if df_result is None or df_result.empty:
                self.show_message("미리보기 실패", "그래프를 그릴 데이터를 추출하지 못했습니다.", error=True)
                self.set_status("미리보기 실패")
                return

            filtered_df = self.current_filter_func()(
                df_result,
                self.append_log,
                self.slope_spin.value(),
                self.max_dist_spin.value(),
                peak_prominence=self.peak_prominence_spin.value(),
            )
            from .plotting import preview_profile

            preview_profile(filtered_df, f"종단면도 미리보기: {os.path.basename(file_path)}")
            self.set_status("그래프 미리보기 완료")
        except Exception as exc:
            self.append_log(f"미리보기 오류: {exc}")
            self.show_message("미리보기 오류", str(exc), error=True)
            self.set_status("미리보기 오류")

    def refresh_pdf_filtered_preview(self):
        if self.pdf_profile_match_df is None or self.pdf_profile_match_df.empty:
            return False

        filtered_df = filter_pdf_graph_points(
            self.pdf_profile_match_df,
            self.append_log,
            self.slope_spin.value(),
            self.max_dist_spin.value(),
            self.peak_prominence_spin.value(),
        )

        if filtered_df.empty:
            self.last_filtered_df = None
            self.clear_inline_result()
            self.set_preview_message("PDF 점 정리 결과가 비어 있습니다.")
            return True

        self.last_filtered_df = filtered_df
        self.last_saved_path = None
        self._populate_table(filtered_df)
        self.draw_inline_preview(filtered_df)

        line_count = 1
        if "line_id" in filtered_df.columns:
            line_count = int(filtered_df["line_id"].nunique())
        elif "라인명" in filtered_df.columns:
            line_count = int(filtered_df["라인명"].nunique())

        page_count = 0
        if "페이지" in filtered_df.columns:
            page_count = int(filtered_df["페이지"].nunique())
        elif "PDF페이지" in filtered_df.columns:
            page_count = int(filtered_df["PDF페이지"].nunique())
        elif self.pdf_region_config:
            page_count = self.pdf_region_config["page_end"] - self.pdf_region_config["page_start"] + 1

        self._update_summary(
            {
                "line_count": line_count,
                "page_count": page_count,
                "quantity_count": int(len(filtered_df)),
            }
        )
        self.set_preview_message("PDF 변환 설정 반영 미리보기")
        self.set_status("PDF 변환 설정 반영 완료")
        self._set_working(False)
        self.apply_responsive_layout()
        return True

    def update_inline_preview(self):
        if not hasattr(self, "preview_canvas"):
            return

        item = self.file_list.currentItem()
        file_path = item.text() if item else (self.selected_files[0] if self.selected_files else "")
        if not file_path:
            self.set_preview_message("미리보기 대기 중")
            self.clear_preview_plot()
            self.clear_inline_result()
            return

        if file_path.lower().endswith(".pdf"):
            if self.refresh_pdf_filtered_preview():
                return
            self.set_preview_message("PDF 영역을 지정하면 미리보기가 표시됩니다.")
            self.clear_preview_plot()
            self.clear_inline_result()
            return

        if not file_path.lower().endswith((".xls", ".xlsx")):
            self.set_preview_message("인라인 미리보기는 Excel 파일을 선택했을 때 표시됩니다.")
            self.clear_preview_plot()
            self.clear_inline_result()
            return

        self.set_preview_message(f"미리보기 계산 중: {os.path.basename(file_path)}")
        try:
            preview_errors = []
            df_result = process_excel_data(file_path, preview_errors.append, self.tolerance_spin.value())
            if df_result is None or df_result.empty:
                detail = preview_errors[-1] if preview_errors else "그래프로 표시할 데이터를 찾지 못했습니다."
                self.set_preview_message(detail)
                self.clear_preview_plot()
                self.clear_inline_result()
                return

            filtered_df = self.current_filter_func()(
                df_result,
                lambda _message: None,
                self.slope_spin.value(),
                self.max_dist_spin.value(),
                peak_prominence=self.peak_prominence_spin.value(),
            )
            self.last_filtered_df = filtered_df
            self.last_saved_path = None
            self.draw_inline_preview(filtered_df)
            self._populate_table(filtered_df)
            self._update_summary(
                {
                    "line_count": 1,
                    "page_count": 0,
                    "quantity_count": int(len(filtered_df)),
                }
            )
            self.set_preview_message(f"선택 파일 미리보기: {os.path.basename(file_path)}")
            self._set_working(False)
            self.apply_responsive_layout()
        except Exception as exc:
            self.set_preview_message(f"미리보기 오류: {exc}")
            self.clear_preview_plot()
            self.clear_inline_result()
            self.apply_responsive_layout()

    def set_preview_message(self, message):
        if hasattr(self, "preview_message"):
            self.preview_message.setText(message)

    def clear_preview_plot(self):
        if not hasattr(self, "preview_figure"):
            return
        self.preview_has_plot = False
        self.preview_figure.clear()
        ax = self.preview_figure.add_subplot(111)
        self.preview_figure.patch.set_facecolor("#172233")
        ax.set_facecolor("#101a29")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_color("#2f3f55")
        self.preview_figure.subplots_adjust(left=0.02, right=0.995, top=0.99, bottom=0.02)
        self.preview_canvas.draw_idle()

    def clear_inline_result(self):
        if hasattr(self, "table"):
            self.table.setRowCount(0)
        self.last_filtered_df = None
        self.last_saved_path = None
        if hasattr(self, "metric_lines"):
            self._update_summary(
                {"line_count": 0, "page_count": 0, "diameter_count": 0, "quantity_count": 0}
            )
        if hasattr(self, "run_button"):
            self._set_working(False)

    def draw_inline_preview(self, df):
        if not hasattr(self, "preview_figure"):
            return

        distance_col = next((col for col in df.columns if "거리" in col), None)
        level_col = next((col for col in df.columns if "고" in col), None)
        if not distance_col or not level_col:
            self.set_preview_message("거리/고도 컬럼을 찾지 못했습니다.")
            self.clear_preview_plot()
            return

        import pandas as pd

        x = pd.to_numeric(df[distance_col].astype(str).str.replace(",", "", regex=False), errors="coerce")
        y = pd.to_numeric(df[level_col].astype(str).str.replace(",", "", regex=False), errors="coerce")
        plot_df = pd.DataFrame({"x": x, "y": y}).dropna()
        if plot_df.empty:
            self.set_preview_message("그래프로 표시할 숫자 데이터가 없습니다.")
            self.clear_preview_plot()
            return

        self.preview_figure.clear()
        self.preview_has_plot = True
        ax = self.preview_figure.add_subplot(111)
        self.preview_figure.patch.set_facecolor("#172233")
        ax.set_facecolor("#101a29")
        if "line_id" in df.columns:
            plot_df["line_id"] = df.loc[plot_df.index, "line_id"].values
            for _line_id, group in plot_df.groupby("line_id", sort=False):
                ax.plot(group["x"], group["y"], marker="o", linewidth=1.8, markersize=4, color="#38bdf8")
                ax.fill_between(group["x"], group["y"], group["y"].min(), color="#256fe6", alpha=0.10)
        else:
            ax.plot(plot_df["x"], plot_df["y"], marker="o", linewidth=1.8, markersize=4, color="#38bdf8")
            ax.fill_between(plot_df["x"], plot_df["y"], plot_df["y"].min(), color="#256fe6", alpha=0.12)
        ax.grid(True, linestyle="--", linewidth=0.7, alpha=0.28, color="#9fb0c8")
        ax.tick_params(colors="#cfe0f8", labelsize=8)
        ax.set_xlabel("누가거리", color="#cfe0f8", fontsize=9, fontproperties=KOREAN_FONT)
        ax.set_ylabel("관저고", color="#cfe0f8", fontsize=9, fontproperties=KOREAN_FONT)
        for spine in ax.spines.values():
            spine.set_color("#2f3f55")
        self.preview_figure.subplots_adjust(left=0.075, right=0.995, top=0.985, bottom=0.16)
        self.preview_canvas.draw_idle()

    def add_files(self, files):
        valid = [f for f in files if os.path.isfile(f) and f.lower().endswith(SUPPORTED_EXTENSIONS)]
        for path in valid:
            if path not in self.selected_files:
                self.selected_files.append(path)
                self.file_list.addItem(path)
        self._set_working(False)
        if valid:
            self.append_log(f"파일 {len(valid)}개 추가됨")
            self.update_inline_preview()

    def remove_selected_files(self):
        selected_rows = sorted(
            [index.row() for index in self.file_list.selectedIndexes()],
            reverse=True,
        )
        if not selected_rows:
            self.show_message("선택 필요", "제거할 파일을 목록에서 선택하세요.", error=True)
            return
        for row in selected_rows:
            self.file_list.takeItem(row)
            if 0 <= row < len(self.selected_files):
                self.selected_files.pop(row)
        self.append_log(f"파일 {len(selected_rows)}개 제거됨")
        self.update_inline_preview()
        self._set_working(False)

    def clear_files(self):
        count = len(self.selected_files)
        self.selected_files = []
        self.pdf_region_config = None
        self.pdf_region_text_df = None
        self.pdf_region_text_items = []
        self.pdf_label_rows = {}
        self.pdf_profile_match_df = None
        self.file_list.clear()
        if count:
            self.append_log(f"파일 목록 전체 비움: {count}개")
        self.set_preview_message("미리보기 대기 중")
        self.clear_preview_plot()
        self.clear_inline_result()
        self._set_working(False)

    def start_analysis(self):
        if not self.selected_files:
            self.show_message("파일 필요", "먼저 PDF 또는 Excel 파일을 선택하세요.", error=True)
            return

        settings = {
            "save_mode": self.current_save_mode(),
            "tolerance": self.tolerance_spin.value(),
            "slope": self.slope_spin.value(),
            "max_dist": self.max_dist_spin.value(),
            "peak_prominence": self.peak_prominence_spin.value(),
            "pdf_start": self.pdf_start_spin.value(),
            "pdf_end": self.pdf_end_spin.value() or None,
        }
        self.log_box.clear()
        self.table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.percent_label.setText("0%")
        self.set_status("변환 중")
        self._set_working(True)

        self.thread = QThread(self)
        self.worker = AnalysisWorker(self.selected_files, settings)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.log.connect(self.append_log)
        self.worker.progress.connect(self.update_progress)
        self.worker.fileDone.connect(self.on_file_done)
        self.worker.error.connect(lambda msg: self.show_message("오류", msg, error=True))
        self.worker.finished.connect(self.on_finished)
        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def update_progress(self, percent, eta_seconds, current_file):
        self.progress_bar.setValue(percent)
        self.percent_label.setText(f"{percent}%")
        self.eta_label.setText(f"예상 남은 시간: {format_seconds(eta_seconds)}")
        self.current_label.setText(current_file or "마무리 중")

    def on_file_done(self, result):
        self.last_filtered_df = result["filtered_df"]
        self.last_saved_path = result["saved_path"]
        self._populate_table(self.last_filtered_df)
        self._update_summary(result["summary"])

    def on_finished(self, payload):
        self._set_working(False)
        self.set_status("완료" if payload["fail"] == 0 else "오류")
        self._update_summary(payload["summary"])
        self.last_filtered_df = payload.get("last_filtered")
        if self.last_filtered_df is not None:
            self._populate_table(self.last_filtered_df)
        self.show_message(
            "변환 완료",
            f"성공 {payload['success']}개 / 실패 {payload['fail']}개",
            error=payload["fail"] > 0,
        )

    def _populate_table(self, df):
        pdf_columns = [
            "line_id",
            "페이지",
            "누가거리",
            "관저고",
            "누가거리 X",
            "관저고 X",
            "원본 누가거리",
            "원본 관저고",
            "상태",
        ]
        if all(column in df.columns for column in pdf_columns):
            display_df = df[pdf_columns].head(300)
            columns = pdf_columns
        else:
            display_df = add_result_column(df).head(300)
            columns = ["관저고", "누가거리", "결과"]
        self.table.setRowCount(len(display_df))
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        for r, (_, row) in enumerate(display_df.iterrows()):
            for c, col in enumerate(columns):
                self.table.setItem(r, c, QTableWidgetItem(str(row.get(col, ""))))

    def copy_table_selection(self):
        ranges = self.table.selectedRanges()
        if not ranges:
            return

        selected_cells = {
            (item.row(), item.column()): item.text()
            for item in self.table.selectedItems()
        }
        min_row = min(r.topRow() for r in ranges)
        max_row = max(r.bottomRow() for r in ranges)
        min_col = min(r.leftColumn() for r in ranges)
        max_col = max(r.rightColumn() for r in ranges)

        lines = []
        for row in range(min_row, max_row + 1):
            values = []
            for col in range(min_col, max_col + 1):
                values.append(selected_cells.get((row, col), ""))
            lines.append("\t".join(values))

        QApplication.clipboard().setText("\n".join(lines))
        self.set_status("선택한 표 데이터를 클립보드에 복사했습니다.")

    def copy_log_to_clipboard(self):
        text = self.log_box.toPlainText().strip()
        if not text:
            self.show_message("복사할 로그 없음", "실행 로그가 비어 있습니다.", error=True)
            return
        QApplication.clipboard().setText(text)
        self.set_status("실행 로그를 클립보드에 복사했습니다.")

    def copy_profile_columns(self):
        if self.last_filtered_df is None or self.last_filtered_df.empty:
            self.show_message("복사할 데이터 없음", "먼저 변환 결과를 미리보거나 변환하세요.", error=True)
            return

        df = self.last_filtered_df
        level_col = next((col for col in df.columns if "고" in col), None)
        distance_col = next((col for col in df.columns if "거리" in col), None)
        if not level_col or not distance_col:
            self.show_message("복사 불가", "관저고/누가거리 컬럼을 찾지 못했습니다.", error=True)
            return

        lines = [
            f"{row[level_col]}\t{row[distance_col]}"
            for _, row in df[[level_col, distance_col]].iterrows()
        ]
        QApplication.clipboard().setText("\n".join(lines))
        self.set_status("관저고/누가거리 전체 행을 클립보드에 복사했습니다.")

    def _update_summary(self, summary):
        self.metric_lines.set_value(summary.get("line_count", 0))
        self.metric_pages.set_value(summary.get("page_count", 0))
        self.metric_quantity.set_value(summary.get("quantity_count", 0))

    def export_excel(self):
        if self.last_saved_path and os.path.exists(self.last_saved_path):
            self.show_message("저장 완료", f"이미 저장된 파일:\n{self.last_saved_path}")
            return
        if self.last_filtered_df is None or self.last_filtered_df.empty:
            self.show_message("저장할 데이터 없음", "변환 완료 후 사용할 수 있습니다.", error=True)
            return
        path, _ = QFileDialog.getSaveFileName(self, "Excel 저장", "결과.xlsx", "Excel files (*.xlsx)")
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        safe_path = safe_output_path(path)
        self._default_result_save_df(self.last_filtered_df).to_excel(safe_path, index=False, engine="openpyxl")
        self.last_saved_path = safe_path
        self.show_message("Excel 저장 완료", safe_path)

    def export_csv(self):
        if self.last_filtered_df is None or self.last_filtered_df.empty:
            self.show_message("저장할 데이터 없음", "변환 완료 후 사용할 수 있습니다.", error=True)
            return
        path, _ = QFileDialog.getSaveFileName(self, "CSV 저장", "결과.csv", "CSV files (*.csv)")
        if not path:
            return
        self._default_result_save_df(self.last_filtered_df).to_csv(path, index=False, encoding="utf-8-sig")
        self.show_message("CSV 저장 완료", path)

    def _default_result_save_df(self, df):
        result_df = add_result_column(df)
        return result_df[["관저고", "누가거리", "결과"]].copy()

    def reset(self):
        self.selected_files = []
        self.pdf_region_config = None
        self.pdf_region_text_df = None
        self.pdf_region_text_items = []
        self.pdf_label_rows = {}
        self.pdf_profile_match_df = None
        self.file_list.clear()
        self.log_box.clear()
        self.table.setRowCount(0)
        self.progress_bar.setValue(0)
        self.percent_label.setText("0%")
        self.eta_label.setText("예상 남은 시간: -")
        self.current_label.setText("대기 중")
        self.last_filtered_df = None
        self.last_saved_path = None
        self._update_summary({"line_count": 0, "page_count": 0, "diameter_count": 0, "quantity_count": 0})
        self.set_preview_message("미리보기 대기 중")
        self.set_status("준비 완료")
        self._set_working(False)

    def append_log(self, message):
        self.log_box.append(f"[{time.strftime('%H:%M:%S')}] {message}")

    def set_status(self, text):
        self.status.showMessage(text)

    def current_save_mode(self):
        text = self.save_combo.currentText()
        if text == "3.3":
            return SAVE_MODE_COMPAT_33
        if text == "3.1":
            return SAVE_MODE_EXTENDED_31
        return SAVE_MODE_COMPAT_24

    def current_filter_func(self):
        return filter_graph_points_33 if self.current_save_mode() == SAVE_MODE_COMPAT_33 else filter_graph_points_24

    def _set_working(self, working):
        has_pdf = any(f.lower().endswith(".pdf") for f in self.selected_files)
        has_excel = any(f.lower().endswith((".xls", ".xlsx")) for f in self.selected_files)
        has_result_data = self.last_filtered_df is not None
        self.run_button.setDisabled(working or not self.selected_files)
        self.reset_button.setDisabled(working)
        self.excel_button.setDisabled(working or not (self.last_saved_path or has_result_data))
        self.csv_button.setDisabled(working or self.last_filtered_df is None)
        self.graph_button.setDisabled(working or not (has_excel or has_result_data))
        self.add_file_button.setDisabled(working)
        self.drop_zone.pdf_region_button.setDisabled(working or not has_pdf)
        self.remove_file_button.setDisabled(working or not self.selected_files)
        self.clear_file_button.setDisabled(working or not self.selected_files)
        if hasattr(self, "copy_profile_button"):
            self.copy_profile_button.setDisabled(working or self.last_filtered_df is None)

    def show_message(self, title, message, error=False):
        box = QMessageBox.critical if error else QMessageBox.information
        box(self, title, message)

    def _show_guide(self):
        self.show_message(
            "사용 가이드",
            "파일 선택 → 변환 설정 → 변환 시작 순서로 사용하세요. 기본 저장 방식은 3.3 호환 저장입니다.",
        )

    def changeEvent(self, event):
        super().changeEvent(event)
        if hasattr(self, "title_bar"):
            self.title_bar.update_maximize_button()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.apply_responsive_layout()

    def apply_responsive_layout(self):
        if not hasattr(self, "main_layout"):
            return
        
        w, h = self.width(), self.height()
        is_narrow = w < 900
        is_compact = h < 600
        
        # 좁은 화면(< 900px)일 때는 수직 스플리터로 변경
        if is_narrow:
            if self.splitter.orientation() != Qt.Vertical:
                self.splitter.setOrientation(Qt.Vertical)
                self.splitter.setSizes([1, 1])
        else:
            if self.splitter.orientation() != Qt.Horizontal:
                self.splitter.setOrientation(Qt.Horizontal)
                self.splitter.setSizes([1, 1])
        
        # 마진 및 간격 조정
        if is_compact:
            self.main_layout.setContentsMargins(8, 6, 8, 4)
            self.main_layout.setSpacing(0)
            self.left_layout.setSpacing(6)
            self.right_layout.setSpacing(6)
            self.splitter.setHandleWidth(4)
            card_margins = (10, 8, 10, 8)
            card_spacing = 6
        else:
            self.main_layout.setContentsMargins(16, 12, 16, 8)
            self.main_layout.setSpacing(0)
            self.left_layout.setSpacing(10)
            self.right_layout.setSpacing(10)
            self.splitter.setHandleWidth(6)
            card_margins = (14, 12, 14, 12)
            card_spacing = 8
        
        # 모든 카드에 동일한 마진 및 간격 적용
        for card in [
            self.file_card,
            self.graph_preview_card,
            self.settings_card,
            self.run_card,
            self.log_card,
            self.result_card,
            self.progress_card,
        ]:
            card.layout.setContentsMargins(*card_margins)
            card.layout.setSpacing(card_spacing)
        
        # 화면 크기에 따른 최소 높이 조정
        if is_compact:
            self.drop_zone.setMinimumHeight(30)
            self.file_list.setMinimumHeight(24)
            self.preview_canvas.setMinimumHeight(50)
            self.table.setMinimumHeight(40)
            self.log_box.setMinimumHeight(30)
        else:
            self.drop_zone.setMinimumHeight(40)
            self.file_list.setMinimumHeight(30)
            self.preview_canvas.setMinimumHeight(80)
            self.table.setMinimumHeight(60)
            self.log_box.setMinimumHeight(40)


class TitleBar(QFrame):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setObjectName("TitleBar")
        self.setFixedHeight(32)
        self._drag_pos = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 8, 4)
        layout.setSpacing(8)

        title = QLabel("▣  CAD PDF Converter Pro - DWG Sort 3.3")
        title.setStyleSheet("font-size: 12px; font-weight: 700; background: transparent;")
        layout.addWidget(title, 1)

        self.min_button = self._window_button("─")
        self.max_button = self._window_button("□")
        self.close_button = self._window_button("×", close=True)

        self.min_button.clicked.connect(self.window.showMinimized)
        self.max_button.clicked.connect(self.toggle_maximized)
        self.close_button.clicked.connect(self.window.close)

        layout.addWidget(self.min_button, 0, Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.max_button, 0, Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self.close_button, 0, Qt.AlignRight | Qt.AlignVCenter)

    def _window_button(self, text, close=False):
        button = QPushButton(text)
        button.setObjectName("CloseButton" if close else "WindowButton")
        button.setCursor(Qt.ArrowCursor)
        return button

    def toggle_maximized(self):
        if self.window.isMaximized():
            self.window.showNormal()
        else:
            self.window.showMaximized()
        self.update_maximize_button()

    def update_maximize_button(self):
        self.max_button.setText("❐" if self.window.isMaximized() else "□")

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle_maximized()
            event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is None or not (event.buttons() & Qt.LeftButton):
            return
        if self.window.isMaximized():
            self.window.showNormal()
            self.update_maximize_button()
            self._drag_pos = QPoint(self.window.width() // 2, 20)
        self.window.move(event.globalPosition().toPoint() - self._drag_pos)
        event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        event.accept()


def format_seconds(seconds):
    seconds = int(seconds or 0)
    if seconds <= 0:
        return "0초"
    minutes, sec = divmod(seconds, 60)
    if minutes:
        return f"{minutes}분 {sec}초"
    return f"{sec}초"


def main():
    app = QApplication(sys.argv)
    apply_fluent_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

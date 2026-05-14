import os
import sys
import time
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QThread
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
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
    DEFAULT_SLOPE_CHANGE,
    DEFAULT_TOLERANCE,
    SAVE_MODE_COMPAT_24,
    SAVE_MODE_EXTENDED_31,
    SUPPORTED_EXTENSIONS,
)
from .excel_compat import add_result_column, filter_graph_points_24, process_excel_data
from .qt_styles import apply_fluent_theme
from .qt_widgets import Card, DropZone, MetricCard, make_button
from .qt_workers import AnalysisWorker


KOREAN_FONT = None
if sys.platform.startswith("win"):
    font_path = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts" / "malgun.ttf"
    if font_path.exists():
        KOREAN_FONT = FontProperties(fname=str(font_path))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setWindowTitle("CAD PDF Converter Pro - DWG Sort 3.1")
        self.resize(1280, 820)
        self.setMinimumSize(600, 500)
        self.selected_files = []
        self.worker = None
        self.thread = None
        self.last_filtered_df = None
        self.last_saved_path = None
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
        layout.setContentsMargins(22, 16, 22, 12)
        layout.setSpacing(12)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(8)

        left_page = QWidget()
        self.left_layout = QVBoxLayout(left_page)
        self.left_layout.setContentsMargins(0, 0, 0, 0)
        self.left_layout.setSpacing(12)
        self.left_layout.addWidget(self._build_file_card(), 0)
        self.left_layout.addWidget(self._build_graph_preview_card(), 10)
        self.left_layout.addWidget(self._build_run_card(), 0)
        self.left_layout.addWidget(self._build_log_card(), 0)

        right_page = QWidget()
        self.right_layout = QVBoxLayout(right_page)
        self.right_layout.setContentsMargins(0, 0, 0, 0)
        self.right_layout.setSpacing(12)
        self.right_layout.addWidget(self._build_result_card(), 10)
        self.right_layout.addWidget(self._build_settings_card(), 0)
        self.right_layout.addWidget(self._build_progress_card(), 0)

        self.splitter.addWidget(left_page)
        self.splitter.addWidget(right_page)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([1, 1])
        layout.addWidget(self.splitter, 1)
        return page

    def _build_file_card(self):
        card = Card("1. PDF/Excel 파일 선택")
        self.file_card = card
        self.drop_zone = DropZone()
        self.drop_zone.setMinimumHeight(52)
        self.drop_zone.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.drop_zone.filesDropped.connect(self.add_files)
        self.drop_zone.chooseClicked.connect(self.choose_files)
        card.layout.addWidget(self.drop_zone)

        self.file_list = QListWidget()
        self.file_list.setMinimumHeight(40)
        self.file_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.file_list.currentItemChanged.connect(lambda _current, _previous: self.update_inline_preview())
        card.layout.addWidget(self.file_list)

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
        card.layout.addLayout(file_actions)
        return card

    def _build_settings_card(self):
        card = Card("2. 변환 설정")
        self.settings_card = card
        self.settings_card.setMinimumHeight(70)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)

        self.save_combo = QComboBox()
        self.save_combo.addItems(["2.4", "3.1"])
        self.save_combo.setCurrentText("2.4")

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
            self.pdf_start_spin,
            self.pdf_end_spin,
        ]:
            control.setFixedHeight(34)
            control.setMinimumWidth(0)
            control.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)

        fields = [
            ("저장", self.save_combo),
            ("Y오차", self.tolerance_spin),
            ("기울기", self.slope_spin),
            ("거리", self.max_dist_spin),
            ("PDF", self._pair_widget(self.pdf_start_spin, self.pdf_end_spin)),
        ]
        for idx, (label, widget) in enumerate(fields):
            box = QHBoxLayout()
            box.setContentsMargins(0, 0, 0, 0)
            box.setSpacing(6)
            caption = QLabel(label)
            caption.setObjectName("Muted")
            caption.setFixedWidth(36)
            box.addWidget(caption)
            box.addWidget(widget, 1)
            widget.setMinimumWidth(0)
            widget.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            grid.addLayout(box, 0, idx)
            grid.setColumnStretch(idx, 1)

        card.layout.addLayout(grid)
        return card

    def _build_graph_preview_card(self):
        card = Card("📊 그래프 미리보기")
        self.graph_preview_card = card
        
        self.preview_message = QLabel("미리보기 대기 중")
        self.preview_message.setObjectName("Muted")
        self.preview_message.setWordWrap(True)
        card.layout.addWidget(self.preview_message)

        self.preview_figure = Figure(figsize=(6, 2.7), dpi=100)
        self.preview_canvas = FigureCanvas(self.preview_figure)
        self.preview_canvas.setMinimumHeight(120)
        self.preview_canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        card.layout.addWidget(self.preview_canvas, 10)
        self.clear_preview_plot()
        
        return card

    def _build_run_card(self):
        card = Card("3. 빠른 실행")
        self.run_card = card
        self.run_card.setMinimumHeight(70)
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
        row.addStretch(1)
        for button in [self.run_button, self.reset_button, self.excel_button, self.csv_button, self.graph_button]:
            button.setFixedHeight(36)
            button.setMinimumWidth(74)
            row.addWidget(button, 0)
        row.addStretch(1)
        card.layout.addLayout(row)
        return card

    def _build_result_card(self):
        card = Card()
        self.result_card = card

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        self.result_title_label = QLabel("변환 결과 미리보기")
        self.result_title_label.setObjectName("SectionTitle")
        header.addWidget(self.result_title_label)
        header.addStretch(1)
        self.copy_profile_button = make_button("복사")
        self.copy_profile_button.setFixedSize(44, 24)
        self.copy_profile_button.clicked.connect(self.copy_profile_columns)
        header.addWidget(self.copy_profile_button)
        card.layout.addLayout(header)

        stats = QGridLayout()
        stats.setHorizontalSpacing(8)
        stats.setVerticalSpacing(0)
        self.metric_lines = MetricCard("총 라인 수")
        self.metric_pages = MetricCard("총 페이지 수")
        self.metric_quantity = MetricCard("총 수량")
        for metric in [self.metric_lines, self.metric_pages, self.metric_quantity]:
            metric.setMaximumHeight(64)
        stats.addWidget(self.metric_lines, 0, 0)
        stats.addWidget(self.metric_quantity, 0, 1)
        stats.addWidget(self.metric_pages, 0, 2)
        card.layout.addLayout(stats)

        self.table = QTableWidget(0, 3)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.setMinimumHeight(90)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectItems)
        self.table.setHorizontalHeaderLabels(["관저고", "누가거리", "결과"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setStyleSheet(
            "QHeaderView::section { background: #263244; color: #dbe7ff; border: 0; border-bottom: 1px solid #34465d; padding: 4px; }"
        )
        copy_shortcut = QShortcut(QKeySequence.Copy, self.table)
        copy_shortcut.activated.connect(self.copy_table_selection)
        card.layout.addWidget(self.table, 1)
        return card

    def _build_log_card(self):
        card = Card("실행 로그")
        self.log_card = card
        self.log_card.setMaximumHeight(150)
        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(54)
        self.log_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        card.layout.addWidget(self.log_box)
        return card

    def _build_progress_card(self):
        card = Card("진행 상황")
        self.progress_card = card
        self.progress_card.setMaximumHeight(150)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
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

    def preview_graph(self):
        if not self.selected_files:
            self.show_message("파일 필요", "먼저 Excel 파일을 선택하세요.", error=True)
            return

        file_path = self.file_list.currentItem().text() if self.file_list.currentItem() else self.selected_files[0]
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

            filtered_df = filter_graph_points_24(
                df_result,
                self.append_log,
                self.slope_spin.value(),
                self.max_dist_spin.value(),
            )
            from .plotting import preview_profile

            preview_profile(filtered_df, f"종단면도 미리보기: {os.path.basename(file_path)}")
            self.set_status("그래프 미리보기 완료")
        except Exception as exc:
            self.append_log(f"미리보기 오류: {exc}")
            self.show_message("미리보기 오류", str(exc), error=True)
            self.set_status("미리보기 오류")

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

            filtered_df = filter_graph_points_24(
                df_result,
                lambda _message: None,
                self.slope_spin.value(),
                self.max_dist_spin.value(),
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
        self.show_message("저장할 데이터 없음", "변환 완료 후 사용할 수 있습니다.", error=True)

    def export_csv(self):
        if self.last_filtered_df is None or self.last_filtered_df.empty:
            self.show_message("저장할 데이터 없음", "변환 완료 후 사용할 수 있습니다.", error=True)
            return
        path, _ = QFileDialog.getSaveFileName(self, "CSV 저장", "결과.csv", "CSV files (*.csv)")
        if not path:
            return
        add_result_column(self.last_filtered_df).to_csv(path, index=False, encoding="utf-8-sig")
        self.show_message("CSV 저장 완료", path)

    def reset(self):
        self.selected_files = []
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
        return SAVE_MODE_EXTENDED_31 if self.save_combo.currentText() == "3.1" else SAVE_MODE_COMPAT_24

    def _set_working(self, working):
        self.run_button.setDisabled(working or not self.selected_files)
        self.reset_button.setDisabled(working)
        self.excel_button.setDisabled(working or not self.last_saved_path)
        self.csv_button.setDisabled(working or self.last_filtered_df is None)
        self.graph_button.setDisabled(working or not any(f.lower().endswith((".xls", ".xlsx")) for f in self.selected_files))
        self.add_file_button.setDisabled(working)
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
            "파일 선택 → 변환 설정 → 변환 시작 순서로 사용하세요. 기본 저장 방식은 2.4 호환 저장입니다.",
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
        compact = self.width() < 1000 or self.height() < 600
        title_visible = self.width() >= 1120 and self.height() >= 680
        action_title_visible = title_visible and self.width() >= 1500 and self.height() >= 780
        metric_lines_visible = self.width() >= 1180 and self.height() >= 700
        metric_pages_visible = self.width() >= 1240 and self.height() >= 730
        metric_quantity_visible = self.width() >= 1320 and self.height() >= 760
        state = (
            compact,
            title_visible,
            action_title_visible,
            self.preview_has_plot,
            metric_lines_visible,
            metric_pages_visible,
            metric_quantity_visible,
        )
        if state == self._compact_mode:
            return
        self._compact_mode = state

        for card in [
            self.file_card,
            self.log_card,
            self.progress_card,
        ]:
            card.set_title_visible(title_visible)
        self.result_title_label.setVisible(title_visible)
        self.graph_preview_card.set_title_visible(title_visible and not self.preview_has_plot)
        self.run_card.set_title_visible(action_title_visible)
        self.settings_card.set_title_visible(action_title_visible)

        self.metric_lines.setVisible(metric_lines_visible)
        self.metric_pages.setVisible(metric_pages_visible)
        self.metric_quantity.setVisible(metric_quantity_visible)
        metric_compact = self.width() < 1450 or self.height() < 820
        for metric in [self.metric_lines, self.metric_pages, self.metric_quantity]:
            metric.set_compact(metric_compact)

        if compact:
            self.main_layout.setContentsMargins(10, 8, 10, 6)
            self.main_layout.setSpacing(6)
            self.left_layout.setSpacing(6)
            self.right_layout.setSpacing(6)
            self.splitter.setHandleWidth(6)
            for card in [
                self.file_card,
                self.graph_preview_card,
                self.run_card,
                self.log_card,
                self.result_card,
                self.settings_card,
                self.progress_card,
            ]:
                card.setMinimumWidth(0)
                card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                card.layout.setContentsMargins(10, 10, 10, 10)
                card.layout.setSpacing(6)
            self.drop_zone.setMinimumHeight(40)
            self.file_list.setMinimumHeight(32)
            self.preview_canvas.setMinimumHeight(72)
            self.table.setMinimumHeight(70)
            self.log_box.setMinimumHeight(48)
            self.preview_message.setVisible(self.preview_has_plot or self.height() >= 520)
        else:
            self.main_layout.setContentsMargins(22, 16, 22, 12)
            self.main_layout.setSpacing(12)
            self.left_layout.setSpacing(12)
            self.right_layout.setSpacing(12)
            self.splitter.setHandleWidth(8)
            for card in [
                self.file_card,
                self.graph_preview_card,
                self.run_card,
                self.log_card,
                self.result_card,
                self.settings_card,
                self.progress_card,
            ]:
                card.setMinimumWidth(0)
                card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
                card.layout.setContentsMargins(18, 18, 18, 18)
                card.layout.setSpacing(12)
            self.drop_zone.setMinimumHeight(52)
            self.file_list.setMinimumHeight(40)
            self.preview_canvas.setMinimumHeight(120)
            self.table.setMinimumHeight(90)
            self.log_box.setMinimumHeight(54)
            self.preview_message.setVisible(True)

        if not action_title_visible:
            for card in [self.run_card, self.settings_card]:
                card.layout.setContentsMargins(10, 8, 10, 8)
                card.layout.setSpacing(6)


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

        title = QLabel("▣  CAD PDF Converter Pro - DWG Sort 3.1")
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

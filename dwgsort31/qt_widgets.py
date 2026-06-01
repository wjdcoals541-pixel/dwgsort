from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


def make_button(text, primary=False, success=False):
    button = QPushButton(text)
    if primary:
        button.setObjectName("PrimaryButton")
    if success:
        button.setObjectName("SuccessButton")
    return button


class Card(QFrame):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.title_label = None
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(14, 12, 14, 12)
        self.layout.setSpacing(8)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumWidth(0)

        if title:
            self.title_label = QLabel(title)
            self.title_label.setObjectName("SectionTitle")
            self.layout.addWidget(self.title_label)

    def set_title_visible(self, visible):
        if self.title_label is not None:
            self.title_label.setVisible(visible)


class MetricCard(QFrame):
    def __init__(self, title, value="0", parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(12, 8, 12, 8)
        self.layout.setSpacing(6)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("Muted")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("MetricValue")

        self.layout.addWidget(self.title_label, 1)
        self.layout.addWidget(self.value_label, 0, Qt.AlignRight | Qt.AlignVCenter)

    def set_value(self, value):
        self.value_label.setText(str(value))

    def set_compact(self, compact):
        if compact:
            self.layout.setContentsMargins(10, 6, 10, 6)
            self.title_label.setStyleSheet("font-size: 11px;")
            self.value_label.setStyleSheet("font-size: 16px; font-weight: 700;")
        else:
            self.layout.setContentsMargins(12, 8, 12, 8)
            self.title_label.setStyleSheet("")
            self.value_label.setStyleSheet("")


class DropZone(QFrame):
    filesDropped = Signal(list)
    chooseClicked = Signal()
    pdfRegionClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setProperty("dragActive", False)

        layout = QHBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        title = QLabel("PDF/Excel 드래그 앤 드롭")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 14px; font-weight: 700;")
        title.setMinimumWidth(0)

        self.choose_button = make_button("선택", primary=True)
        self.choose_button.setFixedHeight(28)
        self.choose_button.setFixedWidth(50)
        self.choose_button.clicked.connect(self.chooseClicked.emit)
        self.pdf_region_button = make_button("PDF 영역 지정")
        self.pdf_region_button.setFixedHeight(28)
        self.pdf_region_button.clicked.connect(self.pdfRegionClicked.emit)

        layout.addWidget(title, 1)
        layout.addWidget(self.choose_button, 0, Qt.AlignCenter)
        layout.addWidget(self.pdf_region_button, 0, Qt.AlignCenter)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            self.setProperty("dragActive", True)
            self.style().unpolish(self)
            self.style().polish(self)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
        event.accept()

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls()]
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
        self.filesDropped.emit(paths)


class FilePill(QWidget):
    def __init__(self, path, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        p = Path(path)
        name = QLabel(p.name)
        name.setStyleSheet("font-weight: 700;")
        detail = QLabel(f"{p.stat().st_size / 1024 / 1024:.2f} MB")
        detail.setObjectName("Muted")
        ok = QLabel("●")
        ok.setStyleSheet("color: #22c55e; font-size: 18px;")

        layout.addWidget(name, 1)
        layout.addWidget(detail)
        layout.addWidget(ok)

APP_QSS = """
QWidget {
    background: #0f1724;
    color: #eef4ff;
    font-family: "Segoe UI", "Malgun Gothic";
    font-size: 13px;
}
QLabel {
    background: transparent;
}
QFrame#Sidebar {
    background: #0a111d;
    border-right: 1px solid #253246;
}
QFrame#TitleBar {
    background: #0a111d;
    border-bottom: 1px solid #1f2c3d;
    border-radius: 12px;
}
QPushButton#WindowButton {
    background: transparent;
    border: 0;
    border-radius: 8px;
    padding: 0px;
    min-width: 28px;
    min-height: 24px;
    max-width: 28px;
    max-height: 24px;
    font-size: 12px;
    font-weight: 500;
}
QPushButton#WindowButton:hover {
    background: #1d2a3d;
}
QPushButton#CloseButton {
    background: transparent;
    border: 0;
    border-radius: 8px;
    padding: 0px;
    min-width: 28px;
    min-height: 24px;
    max-width: 28px;
    max-height: 24px;
    font-size: 12px;
    font-weight: 500;
}
QPushButton#CloseButton:hover {
    background: #c42b1c;
}
QFrame#Card {
    background: #172233;
    border: 1px solid #3a4a62;
    border-radius: 12px;
}
QFrame#DropZone {
    background: #121d2d;
    border: 1px dashed #56667c;
    border-radius: 18px;
}
QFrame#DropZone[dragActive="true"] {
    border: 1px dashed #2f80ed;
    background: #152846;
}
QFrame#PlotFrame {
    background: #101a29;
    border: 1px solid #2f3f55;
    border-radius: 10px;
}
QLabel#Title {
    font-size: 24px;
    font-weight: 800;
    background: transparent;
}
QLabel#SectionTitle {
    font-size: 17px;
    font-weight: 800;
    background: transparent;
}
QLabel#Muted {
    color: #9fb0c8;
    background: transparent;
}
QLabel#MetricValue {
    font-size: 28px;
    font-weight: 800;
    background: transparent;
}
QPushButton {
    background: #263244;
    border: 1px solid #3d4e65;
    border-radius: 9px;
    padding: 5px 7px;
    font-weight: 700;
    min-width: 0px;
}
QPushButton:hover {
    background: #314058;
}
QPushButton:disabled {
    color: #8aa0bc;
    background: #182232;
    border: 1px solid #27364a;
}
QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {
    color: #7f90a8;
    background: #182232;
    border: 1px solid #27364a;
}
QPushButton#PrimaryButton {
    background: #256fe6;
    border: 1px solid #3484ff;
}
QPushButton#PrimaryButton:hover {
    background: #2f80ed;
}
QPushButton#SuccessButton {
    background: #15945a;
    border: 1px solid #22c574;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: #1d2a3d;
    border: 1px solid #34465d;
    border-radius: 6px;
    padding: 8px;
    selection-background-color: #2f80ed;
}
QComboBox::drop-down, QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background: #162235;
    border-left: 1px solid #34465d;
}
QTextEdit, QTableWidget, QListWidget {
    background: #111b2a;
    border: 1px solid #2f3f55;
    border-radius: 7px;
    gridline-color: #2b3a4f;
}
QHeaderView::section {
    background: #263244;
    color: #dbe7ff;
    border: 0;
    border-right: 1px solid #34465d;
    padding: 8px;
    font-weight: 700;
}
QTableCornerButton::section {
    background: #263244;
    border: 0;
    border-bottom: 1px solid #34465d;
    border-right: 1px solid #34465d;
}
QTableWidget::item {
    background: #111b2a;
    color: #eef4ff;
}
QTableWidget::item:selected {
    background: #1f5fbf;
    color: #ffffff;
}
QProgressBar {
    background: #253246;
    border: 0;
    border-radius: 6px;
    min-height: 14px;
    max-height: 14px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background: #2f80ed;
    border-radius: 6px;
}
QStatusBar {
    background: #0a111d;
    color: #cfe0f8;
    border-top: 1px solid #253246;
}
"""


def apply_fluent_theme(app):
    # Keep the runtime on pure PySide6 widgets. Some qfluentwidgets builds
    # initialize QWidget objects during import in this environment.
    app.setStyleSheet(APP_QSS)

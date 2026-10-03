"""Small, separate template conversion window."""
import sys
import os
from pathlib import Path

from PySide6.QtCore import QThread, Signal, QSettings, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QFontDatabase
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QListWidget, QFileDialog, QMessageBox,
    QPlainTextEdit, QDialog)

from dwgsort31.profile_template import convert_file, read_profiles
from dwgsort31.air_valve_dialog import AirValveDialog
from copy import deepcopy

ROOT = Path(__file__).resolve().parent


class Worker(QThread):
    message = Signal(str)
    completed = Signal(int, int)

    def __init__(self, sources, template, output, valve_edits=None):
        super().__init__()
        self.sources, self.template, self.output = sources, template, output
        self.valve_edits = deepcopy(valve_edits or {})

    def run(self):
        count = errors = 0
        for source in self.sources:
            self.message.emit(f'읽는 중: {Path(source).name}')
            try:
                saved = self.valve_edits.get(source)
                if saved and file_signature(source) != saved[0]:
                    raise ValueError('공기밸브 입력 후 원본 파일이 변경됐습니다. 공기밸브 창에서 다시 확인해주세요.')
                count += len(convert_file(source, self.template, self.output, self.message.emit,
                                          edits=saved[1] if saved else None))
            except Exception as error:
                errors += 1
                self.message.emit(f'실패: {Path(source).name}\n{error}')
        self.completed.emit(count, errors)


def file_signature(path):
    stat = Path(path).stat()
    return stat.st_mtime_ns, stat.st_size


class TemplateWindow(QWidget):
    def __init__(self):
        super().__init__()
        font_path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'malgun.ttf'
        if font_path.is_file():
            QFontDatabase.addApplicationFont(str(font_path))
        QApplication.instance().setFont(QFont('Malgun Gothic', 10))
        self.setFont(QFont('Malgun Gothic', 10))
        self.worker = None
        self.valve_edits = {}
        self.settings = QSettings('DWGSort', 'ProfileTemplate')
        self.setWindowTitle('관로종단도 양식 만들기')
        self.resize(800, 590)
        self.setAcceptDrops(True)
        layout = QVBoxLayout(self)
        heading = QLabel('관로종단도 양식 만들기')
        heading.setStyleSheet('font-size:22px; font-weight:600; padding:8px 0;')
        layout.addWidget(heading)
        layout.addWidget(QLabel('누가거리 → 종단면도 거리 · 관저고 → 관저고 · 거리차 자동 계산\n공기밸브를 입력한 지점에 AV 번호와 공기밸브 측점을 반영합니다.'))
        self.template = QLineEdit(str(self.settings.value('template', ROOT / 'templates' / '관로종단도_기준양식.xlsx')))
        self.output = QLineEdit(str(self.settings.value('output', ROOT / '양식변환결과')))
        self.controls = []
        for label, edit, action in [('기준 양식', self.template, self.choose_template), ('저장 폴더', self.output, self.choose_output)]:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            row.addWidget(edit, 1)
            button = QPushButton('찾아보기')
            button.clicked.connect(action)
            row.addWidget(button)
            layout.addLayout(row)
            self.controls.extend([edit, button])
        layout.addWidget(QLabel('입력 파일 (.xls / .xlsx) — 여기에 파일을 끌어다 놓아도 됩니다.'))
        self.files = QListWidget()
        self.files.setSelectionMode(QListWidget.ExtendedSelection)
        layout.addWidget(self.files, 1)
        buttons = QHBoxLayout()
        for label, action in [('파일 추가', self.choose_files), ('선택 제거', self.remove_files)]:
            button = QPushButton(label)
            button.clicked.connect(action)
            buttons.addWidget(button)
            self.controls.append(button)
        buttons.addStretch()
        self.valve_button = QPushButton('공기밸브 지점 편집')
        self.valve_button.clicked.connect(self.edit_valves)
        buttons.addWidget(self.valve_button)
        self.controls.append(self.valve_button)
        self.start = QPushButton('양식 파일 만들기')
        self.start.clicked.connect(self.convert)
        buttons.addWidget(self.start)
        self.controls.append(self.start)
        layout.addLayout(buttons)
        layout.addWidget(QLabel('기준 양식의 표·글꼴·시트·차트 배치를 유지합니다. 차트는 원본처럼 절점 순서로 표시합니다.\n결과 표의 점은 그대로 사용하며, 여러 종단은 각각 파일로 저장합니다.'))
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, 1)
        open_folder = QPushButton('결과 폴더 열기')
        open_folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(self.output.text())))
        layout.addWidget(open_folder)

    def add_files(self, paths):
        existing = {self.files.item(i).text() for i in range(self.files.count())}
        for path in paths:
            if Path(path).suffix.lower() in ('.xls', '.xlsx') and path not in existing:
                self.files.addItem(path)
                existing.add(path)

    def choose_files(self):
        self.add_files(QFileDialog.getOpenFileNames(self, '입력 파일', '', 'Excel (*.xls *.xlsx)')[0])

    def remove_files(self):
        for item in self.files.selectedItems():
            self.valve_edits.pop(item.text(), None)
            self.files.takeItem(self.files.row(item))

    def edit_valves(self):
        items = self.files.selectedItems()
        if len(items) != 1:
            QMessageBox.information(self, '파일 선택', '공기밸브를 입력할 파일 하나를 선택해주세요.')
            return
        source = items[0].text()
        try:
            signature = file_signature(source)
            profiles = read_profiles(source, self.log.appendPlainText)
            saved = self.valve_edits.get(source)
            if saved and saved[0] != signature:
                QMessageBox.warning(self, '원본 변경', '원본 파일이 변경되어 기존 공기밸브 입력을 다시 해야 합니다.')
                saved = None
            dialog = AirValveDialog(profiles, saved[1] if saved else {}, self)
            if dialog.exec() == QDialog.Accepted:
                self.valve_edits[source] = (signature, dialog.edits)
                count = sum(len(v) for v in dialog.edits.values())
                self.log.appendPlainText(f'{Path(source).name}: 공기밸브 {count}개 반영 대기 — 양식 파일 만들기를 눌러 저장하세요.')
        except Exception as error:
            QMessageBox.warning(self, '읽기 오류', str(error))

    def choose_template(self):
        path = QFileDialog.getOpenFileName(self, '기준 양식 선택', '', 'Excel (*.xlsx)')[0]
        if path:
            self.template.setText(path)

    def choose_output(self):
        path = QFileDialog.getExistingDirectory(self, '결과 저장 폴더', self.output.text())
        if path:
            self.output.setText(path)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and not (self.worker and self.worker.isRunning()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        self.add_files([url.toLocalFile() for url in event.mimeData().urls()])

    def convert(self):
        if not self.files.count() or not Path(self.template.text()).is_file() or not self.output.text().strip():
            QMessageBox.warning(self, '선택 확인', '입력 파일, 기준 양식, 저장 폴더를 선택해주세요.')
            return
        self.settings.setValue('template', self.template.text())
        self.settings.setValue('output', self.output.text())
        for control in self.controls:
            control.setEnabled(False)
        self.worker = Worker([self.files.item(i).text() for i in range(self.files.count())], self.template.text(), self.output.text(), self.valve_edits)
        self.worker.message.connect(self.log.appendPlainText)
        self.worker.completed.connect(self.finished)
        self.worker.start()

    def finished(self, count, errors):
        for control in self.controls:
            control.setEnabled(True)
        self.log.appendPlainText(f'작업 완료: 생성 {count}개 / 실패 {errors}개')

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            QMessageBox.information(self, '변환 중', '파일 저장이 끝난 뒤 닫아주세요.')
            event.ignore()
        else:
            if any(records for _, edits in self.valve_edits.values() for records in edits.values()):
                if QMessageBox.question(self, '종료 확인', '공기밸브 입력은 현재 실행 중에만 유지됩니다. 필요한 엑셀을 저장했다면 종료해주세요.\n종료할까요?', QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                    event.ignore()
                    return
            event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = TemplateWindow()
    window.show()
    sys.exit(app.exec())

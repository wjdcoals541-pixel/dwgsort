from copy import deepcopy
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QTableWidget, QTableWidgetItem, QAbstractItemView, QPushButton,
    QLineEdit, QDialogButtonBox, QMessageBox, QInputDialog, QLabel, QHeaderView)
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from .air_valves import valve_values, merge_valves


class ValveInput(QDialog):
    def __init__(self, parent, record=None):
        super().__init__(parent)
        self.setWindowTitle('공기밸브 지점 입력')
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.fields = {}
        for key, label in [('distance', '누가거리 (m)'), ('elevation', '관저고 (m)'), ('station', '공기밸브 측점'), ('av', 'AV 번호')]:
            field = QLineEdit('' if record is None else str(record[key]))
            self.fields[key] = field
            form.addRow(label, field)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def validate(self):
        try:
            self.record = valve_values(**{k: v.text() for k, v in self.fields.items()})
        except ValueError as error:
            QMessageBox.warning(self, '입력 확인', str(error))
            return
        self.accept()


class AirValveDialog(QDialog):
    def __init__(self, profiles, edits, parent=None):
        super().__init__(parent)
        self.profiles = profiles
        self.edits = deepcopy(edits)
        self.setWindowTitle('공기밸브 지점 추가 · 수정 · 삭제')
        self.resize(940, 760)
        layout = QVBoxLayout(self)
        self.profile = QComboBox()
        for name, points in profiles:
            self.profile.addItem(f'{name} ({len(points)}개 원본 지점)')
        layout.addWidget(self.profile)
        layout.addWidget(QLabel('종단을 선택한 뒤 공기밸브 지점을 입력하세요. 수정·삭제는 밸브가 있는 행을 선택합니다.'))
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(['절점', '누가거리', '관저고', '거리차', 'AV 번호', '공기밸브 측점'])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table, 2)
        row = QHBoxLayout()
        for text, callback in [('공기밸브 지점 추가', self.add_valve), ('선택 밸브 수정', self.edit_valve), ('선택 밸브 삭제', self.delete_valve)]:
            button = QPushButton(text)
            button.clicked.connect(callback)
            row.addWidget(button)
        layout.addLayout(row)
        self.figure = Figure(figsize=(8, 2), tight_layout=True)
        self.canvas = FigureCanvasQTAgg(self.figure)
        layout.addWidget(self.canvas, 1)
        layout.addWidget(QLabel('미리보기는 실제 누가거리 기준입니다. 저장되는 엑셀 차트는 기존 양식의 절점 순서 표시를 유지합니다.\n기존 지점에 붙인 밸브를 삭제하면 원본 관저고로 복원합니다. 새로 삽입한 밸브는 지점도 삭제합니다.'))
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText('입력 반영')
        buttons.button(QDialogButtonBox.Cancel).setText('취소')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.profile.currentIndexChanged.connect(self.refresh)
        self.refresh()

    def current(self):
        name, points = self.profiles[self.profile.currentIndex()]
        return points, self.edits.setdefault(name, [])

    def refresh(self):
        points, valves = self.current()
        self.rows = merge_valves(points, valves)
        self.table.setRowCount(len(self.rows))
        for i, row in enumerate(self.rows):
            delta = row['distance'] - self.rows[i-1]['distance'] if i else 0
            values = [f'J-{i+1}', f"{row['distance']:g}", f"{row['elevation']:g}", f'{delta:g}', row['av'], row['station']]
            for c, value in enumerate(values):
                self.table.setItem(i, c, QTableWidgetItem(value))
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.plot([r['distance'] for r in self.rows], [r['elevation'] for r in self.rows], marker='.', linewidth=1)
        marked = [r for r in self.rows if r['av']]
        ax.scatter([r['distance'] for r in marked], [r['elevation'] for r in marked], color='red', zorder=3)
        ax.set_xlabel('Distance (m)')
        ax.set_ylabel('Elevation (m)')
        ax.grid(alpha=.25)
        self.canvas.draw_idle()

    def selected_valve(self):
        row = self.table.currentRow()
        if row < 0 or self.rows[row]['valve_index'] is None:
            QMessageBox.information(self, '선택 확인', 'AV 번호가 있는 행을 선택해주세요.')
            return None
        return self.rows[row]['valve_index']

    def add_valve(self):
        self.input_valve()

    def edit_valve(self):
        index = self.selected_valve()
        if index is not None:
            self.input_valve(index)

    def input_valve(self, index=None):
        points, valves = self.current()
        old = valves[index] if index is not None else None
        dialog = ValveInput(self, old)
        if dialog.exec() != QDialog.Accepted:
            return
        value = dialog.record
        others = [v for i, v in enumerate(valves) if i != index]
        if any(v['distance'] == value['distance'] for v in others):
            QMessageBox.warning(self, '같은 위치의 밸브', '같은 누가거리의 밸브가 있습니다. 해당 밸브를 수정해주세요.')
            return
        matches = [i for i, p in enumerate(points) if p[0] == value['distance']]
        if old is not None and old['distance'] == value['distance']:
            value['base_index'] = old['base_index']
        elif matches:
            answer = QMessageBox.question(self, '기존 지점과 같은 거리',
                '기존 지점에 밸브 정보를 붙이고 입력한 관저고를 적용할까요?\n예: 기존 지점 사용 / 아니요: 같은 거리에 별도 지점 삽입',
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel, QMessageBox.Yes)
            if answer == QMessageBox.Cancel:
                return
            if answer == QMessageBox.Yes:
                chosen = matches[0]
                if len(matches) > 1:
                    choices = [f'원본 지점 {i+1} / 관저고 {points[i][1]:g}' for i in matches]
                    text, ok = QInputDialog.getItem(self, '기존 지점 선택', '밸브를 붙일 지점', choices, 0, False)
                    if not ok:
                        return
                    chosen = matches[choices.index(text)]
                value['base_index'] = chosen
        if index is None:
            valves.append(value)
        else:
            valves[index] = value
        self.refresh()

    def delete_valve(self):
        index = self.selected_valve()
        if index is not None:
            self.current()[1].pop(index)
            self.refresh()

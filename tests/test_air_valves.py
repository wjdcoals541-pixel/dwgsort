import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import patch
from xml.dom import minidom
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from dwgsort31.air_valves import valve_values, merge_valves
from dwgsort31.air_valve_dialog import AirValveDialog, ValveInput
from dwgsort31.profile_template import fill_sheet
from test_profile_template import fixture_sheet


class ValveTests(unittest.TestCase):
    def setUp(self):
        self.points = [(0, 23.51), (3, 23.51), (12, 23.49)]

    def test_insert_and_remove_restores_original(self):
        v = valve_values(9, 23.5, 'AIR-1', 'No. 0+9')
        rows = merge_valves(self.points, [v])
        self.assertEqual([r['distance'] for r in rows], [0, 3, 9, 12])
        self.assertEqual(rows[2]['av'], 'AIR-1')
        self.assertEqual([(r['distance'], r['elevation']) for r in merge_valves(self.points, [])], self.points)

    def test_attach_changes_elevation_without_extra_point(self):
        v = valve_values(3, 23.6, 'AIR-2', 'No. 0+3', 1)
        rows = merge_valves(self.points, [v])
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[1]['elevation'], 23.6)
        self.assertEqual(self.points[1][1], 23.51)

    def test_numeric_validation(self):
        for d, e, av, station in [(-1, 3, 'A', 'N'), ('', 1, 'A', 'N'), (0, float('nan'), 'A', 'N'), (0, 1, '', 'N'), (0, 1, 'A', '')]:
            with self.assertRaises(ValueError):
                valve_values(d, e, av, station)

    def test_export_valve_cells_and_distance_difference(self):
        rows = merge_valves(self.points, [valve_values(9, 23.5, 'AIR-1', 'No. 0+9')])
        pairs = [(r['distance'], r['elevation']) for r in rows]
        doc = minidom.parseString(fill_sheet(fixture_sheet(), pairs, 'Test', valves={2: rows[2]}))
        cells = {c.getAttribute('r'): c for c in doc.getElementsByTagName('c')}
        self.assertEqual(cells['H7'].getElementsByTagName('t')[0].firstChild.data, 'AIR-1')
        self.assertEqual(cells['I7'].getElementsByTagName('t')[0].firstChild.data, 'No. 0+9')
        self.assertEqual(cells['E7'].getElementsByTagName('v')[0].firstChild.data, '6')
        self.assertFalse(cells['F7'].childNodes)
        self.assertFalse(cells['G7'].childNodes)

    def test_dialog_add_edit_delete_and_profile_isolation(self):
        app = QApplication.instance() or QApplication([])
        dialog = AirValveDialog([('one', self.points), ('two', [(0, 10)])], {})
        values = valve_values(9, 23.5, 'AIR-1', 'No. 0+9')
        def accept_input(instance):
            instance.record = values.copy()
            return QDialog.Accepted
        with patch.object(ValveInput, 'exec', accept_input):
            dialog.add_valve()
        self.assertEqual(dialog.table.item(2, 4).text(), 'AIR-1')
        self.assertEqual(list(dialog.figure.axes[0].lines[0].get_xdata()), [0, 3, 9, 12])
        dialog.table.selectRow(2)
        values = valve_values(3, 24, 'AIR-2', 'No. 0+3')
        with patch.object(ValveInput, 'exec', accept_input), patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
            dialog.edit_valve()
        self.assertEqual(len(dialog.rows), 3)
        self.assertEqual(dialog.rows[1]['elevation'], 24)
        dialog.profile.setCurrentIndex(1)
        self.assertEqual(len(dialog.rows), 1)
        self.assertEqual(dialog.rows[0]['av'], '')
        dialog.profile.setCurrentIndex(0)
        dialog.table.selectRow(1)
        dialog.delete_valve()
        self.assertEqual(dialog.rows[1]['elevation'], 23.51)
        self.assertEqual(dialog.edits['one'], [])
        dialog.close()

    def test_dialog_cancel_does_not_mutate_caller(self):
        app = QApplication.instance() or QApplication([])
        edits = {'one': [valve_values(3, 24, 'AIR-1', 'No. 0+3', 1)]}
        dialog = AirValveDialog([('one', self.points)], edits)
        dialog.table.selectRow(1)
        dialog.delete_valve()
        dialog.reject()
        self.assertEqual(len(edits['one']), 1)

    def test_main_edit_button_accepts_changes(self):
        from profile_template_app import TemplateWindow
        app = QApplication.instance() or QApplication([])
        window = TemplateWindow()
        window.add_files(['input.xlsx'])
        window.files.setCurrentRow(0)
        def accept(dialog):
            dialog.edits['one'] = [valve_values(9, 23.5, 'AIR-1', 'No. 0+9')]
            return QDialog.Accepted
        with patch('profile_template_app.read_profiles', return_value=[('one', self.points)]), patch('profile_template_app.file_signature', return_value=(1, 2)), patch.object(AirValveDialog, 'exec', accept), patch.object(QMessageBox, 'warning') as warning:
            window.valve_button.click()
            warning.assert_not_called()
        self.assertEqual(window.valve_edits['input.xlsx'][1]['one'][0]['av'], 'AIR-1')
        window.valve_edits.clear()
        window.close()

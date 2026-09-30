import unittest
from unittest.mock import patch
from xml.dom import minidom
import pandas as pd

from dwgsort31.profile_template import normalize_points, read_profiles, fill_sheet, update_chart


def fixture_sheet():
    rows = []
    for r in range(1, 30):
        cells = ''.join(f'<c r="{c}{r}" s="7"><v>123</v></c>' for c in 'ABCDEFGHIJKL')
        rows.append(f'<row r="{r}" ht="30" customHeight="1">{cells}</row>')
    return ('<worksheet><dimension ref="A1:L29"/><sheetData>' + ''.join(rows) +
            '</sheetData><mergeCells><mergeCell ref="A27:B27"/></mergeCells></worksheet>').encode()


class TemplateTests(unittest.TestCase):
    def test_input_numbers_and_duplicate_chainage_preserved(self):
        points = normalize_points(pd.DataFrame({'누가거리': ['0', '1,000', '1,000'], '관저고': ['23.51', '2', '3']}))
        self.assertEqual(points, [(0, 23.51), (1000, 2), (1000, 3)])

    def test_invalid_and_decreasing_values_rejected(self):
        for distances in [[0, -1], [2, 1], [0, float('nan')], [0, 'x']]:
            with self.assertRaises(ValueError):
                normalize_points(pd.DataFrame({'누가거리': distances, '관저고': [1, 2]}))

    def test_result_file_alias_and_separate_profiles(self):
        frame = pd.DataFrame({'추가거리': [0, 3, 0], '관저고': [23.51, 23.49, 12], 'line_id': [1, 1, 2]})
        with patch('dwgsort31.profile_template.read_bytes', return_value=b'file'), patch('dwgsort31.profile_template.pd.read_excel', return_value={'Sheet1': frame}):
            result = read_profiles('test.xlsx')
        self.assertEqual([p for _, p in result], [[(0, 23.51), (3, 23.49)], [(0, 12)]])

    def test_template_expands_and_shrinks_with_blanks_and_formulas(self):
        for size in [1, 3, 22, 73]:
            points = [(10 + i*3, 23.51-i*.01) for i in range(size)]
            doc = minidom.parseString(fill_sheet(fixture_sheet(), points, '제목'))
            cells = {c.getAttribute('r'): c for c in doc.getElementsByTagName('c')}
            self.assertEqual(cells['C5'].getElementsByTagName('v')[0].firstChild.data, '23.51')
            self.assertEqual(cells['D5'].getElementsByTagName('v')[0].firstChild.data, '10')
            for row in range(5, size+5):
                for col in 'FGHIJ':
                    self.assertFalse(cells[f'{col}{row}'].childNodes)
                self.assertEqual(cells[f'C{row}'].getAttribute('s'), '7')
            self.assertEqual(cells[f'E{size+5}'].getElementsByTagName('f')[0].firstChild.data, f'SUM(E5:E{size+4})')
            self.assertEqual(doc.getElementsByTagName('mergeCell')[0].getAttribute('ref'), f'A{size+5}:B{size+5}')

    def test_chart_cache_and_axis_bounds(self):
        chart = b'<c:chartSpace xmlns:c="chart"><c:chart><c:strRef><c:f>sheet!$B$5:$B$26</c:f><c:strCache/></c:strRef><c:numRef><c:f>sheet!$C$5:$C$26</c:f><c:numCache/></c:numRef><c:valAx><c:scaling><c:min val="-5"/><c:max val="15"/></c:scaling></c:valAx></c:chart></c:chartSpace>'
        doc = minidom.parseString(update_chart(chart, [(0, 23.51), (3, 23.49)], '제목'))
        self.assertFalse(doc.getElementsByTagName('c:max'))
        self.assertEqual([n.getAttribute('val') for n in doc.getElementsByTagName('c:ptCount')], ['2', '2'])
        self.assertEqual([n.firstChild.data for n in doc.getElementsByTagName('c:v')], ['J-1', 'J-2', '23.51', '23.49'])


if __name__ == '__main__':
    unittest.main()

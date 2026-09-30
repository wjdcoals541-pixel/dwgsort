import unittest
from unittest.mock import patch

import pandas as pd

from dwgsort31.excel_compat import process_excel_data, filter_graph_points_24
from dwgsort31.excel_compat33 import filter_graph_points_33
from dwgsort31.excel_input import read_excel_extraction
from dwgsort31.utils import result_columns


def layer_frame(label="누가거리"):
    rows = []
    for offset, levels in [(0, (5, 6, 7)), (100, (20, 21, 22))]:
        for i, elevation in enumerate(levels):
            x = offset + i * 10
            rows.extend([
                [str(i * 10), f"{x},0", label],
                [str(elevation), f"{x},15", "관저고박스"],
                ["999", f"{x},5", "지반고"],
                ["888", f"{x},30", "관저고원"],
            ])
    return pd.DataFrame(rows, columns=["컨텐츠", "위치", "도면층"])


class ExcelInputTests(unittest.TestCase):
    def read(self, sheets):
        with patch("dwgsort31.excel_input.pd.read_excel", return_value=sheets):
            return process_excel_data("sample.xls", lambda message: None, 5)

    def test_english_and_korean_label_formats(self):
        for label in ("누가거리", "추가거리"):
            for columns in (("Contents", "Position"), ("컨텐츠", "위치")):
                with self.subTest(label=label, columns=columns):
                    frame = pd.DataFrame([
                        [label, "0,0"], ["관저고", "0,20"],
                        ["0", "10,0"], ["10", "20,0"],
                        ["5", "10,20"], ["6", "20,20"],
                    ], columns=columns)
                    result = self.read({"Sheet1": frame})
                    self.assertEqual(result["관저고"].tolist(), ["5", "6"])
                    self.assertEqual(result["누가거리"].tolist(), ["0", "10"])

    def test_layer_profiles_preserve_values_and_repeated_chainages(self):
        for label in ("누가거리", "추가거리"):
            with self.subTest(label=label):
                result = self.read({"Sheet1": layer_frame(label)})
                self.assertEqual(result["관저고"].tolist(), ["5", "6", "7", "20", "21", "22"])
                self.assertEqual(result["누가거리"].tolist(), ["0", "10", "20"] * 2)
                self.assertEqual(result["line_id"].tolist(), [1] * 3 + [2] * 3)
                for filter_func in (filter_graph_points_24, filter_graph_points_33):
                    filtered = filter_func(result, lambda message: None, 0.03, 100)
                    self.assertEqual(filtered.groupby("line_id")["관저고"].first().tolist(), ["5", "20"])
                    self.assertEqual(filtered.groupby("line_id")["관저고"].last().tolist(), ["7", "22"])
                    self.assertIn("line_id", result_columns(filtered))

    def test_split_coordinates_and_mixed_sheets(self):
        korean = layer_frame()
        english = korean.rename(columns={"컨텐츠": "Contents", "도면층": "Layer"}).copy()
        english[["Position: X", "Position: Y"]] = english.pop("위치").str.split(",", expand=True)
        result = self.read({"Korean": korean, "English": english})
        self.assertEqual(len(result), 12)
        self.assertEqual(result["line_id"].nunique(), 4)

    def test_stacked_profiles_do_not_cross_match(self):
        first = layer_frame().iloc[:12].copy()
        second = first.copy()
        second["위치"] = second["위치"].map(lambda v: f"{v.split(',')[0]},{float(v.split(',')[1]) + 100}")
        second.loc[second["도면층"].eq("관저고박스"), "컨텐츠"] = ["30", "31", "32"]
        result = self.read({"Sheet1": pd.concat([first, second], ignore_index=True)})
        self.assertEqual(result.groupby("line_id")["관저고"].first().tolist(), ["30", "5"])

    def test_unknown_layers_are_not_guessed(self):
        frame = layer_frame().assign(도면층="미확인")
        self.assertIsNone(self.read({"Sheet1": frame}))

    def test_conflicting_elevations_fail_instead_of_guessing(self):
        frame = layer_frame()
        duplicate = frame.iloc[[1]].copy()
        duplicate["컨텐츠"] = "123"
        with self.assertRaisesRegex(ValueError, "서로 다른 관저고"):
            self.read({"Sheet1": pd.concat([frame, duplicate], ignore_index=True)})

    def test_missing_columns_report_required_data(self):
        with patch("dwgsort31.excel_input.pd.read_excel", return_value={"Sheet1": pd.DataFrame({"Other": [1]})}):
            with self.assertRaisesRegex(ValueError, "컨텐츠"):
                read_excel_extraction("sample.xls", lambda message: None)


if __name__ == "__main__":
    unittest.main()

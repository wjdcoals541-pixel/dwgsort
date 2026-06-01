import os
import time
import math

from PySide6.QtCore import QObject, Signal, Slot

from .config import DEFAULT_TOLERANCE, SAVE_MODE_COMPAT_33, SAVE_MODE_EXTENDED_31, SUPPORTED_EXCEL_EXTENSIONS
from .dxf_vector_parser import process_dxf_profile
from .excel_compat import filter_graph_points_24, process_excel_data, save_compat_24_excel
from .excel_compat33 import filter_graph_points_33, save_compat_33_excel
from .extended_save import save_extended_31_excel
from .pdf_lazy import process_pdf_with_30
from .pdf_point_filter import filter_pdf_graph_points



class AnalysisWorker(QObject):
    log = Signal(str)
    progress = Signal(int, int, str)
    fileDone = Signal(dict)
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, files, settings):
        super().__init__()
        self.files = list(files)
        self.settings = dict(settings)
        self._cancelled = False
        self._started_at = None

    def cancel(self):
        self._cancelled = True

    def _emit_progress(self, percent, current_file=""):
        percent = max(0, min(100, int(percent)))
        elapsed = max(0.1, time.time() - self._started_at)
        if 0 < percent < 100:
            eta = max(0, int(elapsed / (percent / 100) - elapsed))
        else:
            eta = 0
        self.progress.emit(percent, eta, current_file)

    def _log(self, message):
        self.log.emit(str(message))

    @Slot()
    def run(self):
        self._started_at = time.time()
        total = max(1, len(self.files))
        success = 0
        fail = 0
        outputs = []
        last_raw = None
        last_filtered = None

        self._emit_progress(1, "")
        for index, file_path in enumerate(self.files, start=1):
            if self._cancelled:
                self._log("사용자 요청으로 작업을 중단했습니다.")
                break

            file_name = os.path.basename(file_path)
            base = int(((index - 1) / total) * 100)
            span = max(1, int(100 / total))

            try:
                self._log(f"{file_name} 변환 시작")
                self._emit_progress(base + span * 0.12, file_name)

                lower = file_path.lower()
                if lower.endswith(SUPPORTED_EXCEL_EXTENSIONS):
                    raw_df = process_excel_data(
                        file_path, self._log, self.settings["tolerance"]
                    )
                elif lower.endswith(".pdf"):
                    raw_df = process_pdf_with_30(
                        file_path,
                        self._log,
                        DEFAULT_TOLERANCE,
                        self.settings.get("pdf_start"),
                        self.settings.get("pdf_end"),
                    )
                elif lower.endswith(".dxf"):
                    _text_df, raw_df = process_dxf_profile(file_path, self._log)
                else:
                    raise ValueError("지원하지 않는 파일 형식입니다.")

                self._emit_progress(base + span * 0.55, file_name)
                if raw_df is None or raw_df.empty:
                    raise ValueError("추출된 데이터가 없습니다.")

                if lower.endswith((".pdf", ".dxf")):
                    filtered_df = filter_pdf_graph_points(
                        raw_df,
                        self._log,
                        self.settings["slope"],
                        self.settings["max_dist"],
                        self.settings.get("peak_prominence", 0.30),
                    )
                    filtered_df = apply_distance_rounding_filter(
                        filtered_df,
                        self.settings.get("round_distance", False),
                        self._log,
                    )
                else:
                    filter_func = (
                        filter_graph_points_33
                        if self.settings["save_mode"] == SAVE_MODE_COMPAT_33
                        else filter_graph_points_24
                    )
                    filtered_df = filter_func(
                        raw_df,
                        self._log,
                        self.settings["slope"],
                        self.settings["max_dist"],
                        peak_prominence=self.settings.get("peak_prominence", 0.30),
                    )
                    filtered_df = apply_distance_rounding_filter(
                        filtered_df,
                        self.settings.get("round_distance", False),
                        self._log,
                    )
                self._emit_progress(base + span * 0.78, file_name)

                output_path = os.path.join(
                    os.path.dirname(file_path),
                    f"결과_{os.path.splitext(file_name)[0]}.xlsx",
                )
                if self.settings["save_mode"] == SAVE_MODE_EXTENDED_31:
                    saved_path = save_extended_31_excel(raw_df, filtered_df, output_path)
                elif self.settings["save_mode"] == SAVE_MODE_COMPAT_33:
                    saved_path = save_compat_33_excel(filtered_df, output_path)
                else:
                    saved_path = save_compat_24_excel(filtered_df, output_path)

                result = {
                    "file": file_path,
                    "saved_path": saved_path,
                    "raw_rows": int(len(raw_df)),
                    "filtered_rows": int(len(filtered_df)),
                    "summary": build_summary(raw_df, filtered_df),
                    "filtered_df": filtered_df,
                }
                outputs.append(result)
                last_raw = raw_df
                last_filtered = filtered_df
                success += 1
                self.fileDone.emit(result)
                self._log(f"{os.path.basename(saved_path)} 저장 완료")
                self._emit_progress(base + span, file_name)
            except Exception as exc:
                fail += 1
                message = f"{file_name} 처리 오류: {exc}"
                self._log(message)
                self.error.emit(message)

        summary = merge_summaries([item["summary"] for item in outputs])
        self._emit_progress(100, "")
        self.finished.emit(
            {
                "success": success,
                "fail": fail,
                "outputs": outputs,
                "summary": summary,
                "last_raw": last_raw,
                "last_filtered": last_filtered,
            }
        )


def apply_distance_rounding_filter(df, enabled, log_func):
    if df is None or df.empty or not enabled or "누가거리" not in df.columns:
        return df

    result_df = df.copy()
    group_col = None
    if "line_id" in result_df.columns:
        group_col = "line_id"
    elif "라인명" in result_df.columns:
        group_col = "라인명"

    keep_indexes = []
    seen = set()
    removed_count = 0

    for index, row in result_df.iterrows():
        numeric_distance = parse_numeric_distance(row.get("누가거리"))
        if numeric_distance is None:
            keep_indexes.append(index)
            continue

        rounded_distance = math.ceil(numeric_distance)
        line_key = row.get(group_col) if group_col else "all"
        duplicate_key = (line_key, rounded_distance)
        if duplicate_key in seen:
            removed_count += 1
            continue

        seen.add(duplicate_key)
        result_df.at[index, "누가거리"] = str(rounded_distance)
        keep_indexes.append(index)

    result_df = result_df.loc[keep_indexes].copy()
    if "증가거리" in result_df.columns:
        result_df = recalculate_increase_distance(result_df)

    log_func(f"[올림설정] 누가거리 정수 올림 적용: 중복 {removed_count}행 제거")
    return result_df


def recalculate_increase_distance(df):
    result_df = df.copy()
    group_col = None
    if "line_id" in result_df.columns:
        group_col = "line_id"
    elif "라인명" in result_df.columns:
        group_col = "라인명"
    groups = result_df.groupby(group_col, sort=False) if group_col else [("all", result_df)]
    result_df["증가거리"] = "-"

    for _, group_df in groups:
        previous = None
        for index, value in group_df["누가거리"].items():
            current = parse_numeric_distance(value)
            if current is None:
                previous = None
                continue
            if previous is not None:
                result_df.at[index, "증가거리"] = f"{current - previous:.0f}"
            previous = current

    return result_df


def parse_numeric_distance(value):
    try:
        return float(str(value).strip().replace(",", ""))
    except (TypeError, ValueError):
        return None


def build_summary(raw_df, filtered_df):
    def unique_count(column):
        if column in raw_df.columns:
            return int(raw_df[column].dropna().astype(str).str.strip().replace("", None).nunique())
        return 0

    total_pages = 0
    if "PDF페이지" in raw_df.columns:
        pages = raw_df["PDF페이지"].dropna()
        total_pages = int(pages.nunique()) if not pages.empty else 0
    elif "페이지" in raw_df.columns:
        pages = raw_df["페이지"].dropna()
        total_pages = int(pages.nunique()) if not pages.empty else 0
    elif "DXF페이지" in raw_df.columns:
        pages = raw_df["DXF페이지"].dropna()
        total_pages = int(pages.nunique()) if not pages.empty else 0

    return {
        "line_count": unique_count("라인명") or unique_count("line_id") or 1,
        "page_count": total_pages,
        "diameter_count": unique_count("관경") or unique_count("환경"),
        "quantity_count": int(len(filtered_df)),
    }


def merge_summaries(summaries):
    if not summaries:
        return {"line_count": 0, "page_count": 0, "diameter_count": 0, "quantity_count": 0}
    return {
        "line_count": sum(item.get("line_count", 0) for item in summaries),
        "page_count": sum(item.get("page_count", 0) for item in summaries),
        "diameter_count": max(item.get("diameter_count", 0) for item in summaries),
        "quantity_count": sum(item.get("quantity_count", 0) for item in summaries),
    }

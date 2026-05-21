from __future__ import annotations

import math
import re
from dataclasses import dataclass

import pandas as pd

from .config import (
    PDF_REGION_PAD_BOTTOM,
    PDF_REGION_PAD_LEFT,
    PDF_REGION_PAD_RIGHT,
    PDF_REGION_PAD_TOP,
    PDF_ROW_CLUSTER_TOLERANCE,
    PDF_X_TOLERANCE,
    PDF_Y_TOLERANCE,
)


@dataclass
class PdfTextItem:
    page: int
    contents: str
    x: float
    y: float
    bbox: tuple[float, float, float, float]
    rotation: int

    @property
    def position(self):
        return f"{self.x:.2f},{self.y:.2f}"

    def to_record(self):
        return {
            "page": self.page,
            "contents": self.contents,
            "x": self.x,
            "y": self.y,
            "bbox": self.bbox,
            "rotation": self.rotation,
        }

    def to_excel_like_record(self):
        return {
            "PDF페이지": self.page,
            "Contents": self.contents,
            "Position": self.position,
            "X": self.x,
            "Y": self.y,
            "BBox": self.bbox,
            "Rotation": self.rotation,
        }


@dataclass
class PdfLabel:
    page: int
    name: str
    x: float
    y: float
    contents: str
    source: str


def extract_pdf_region_text(file_path, region_config, log_func):
    """Extract vector text objects inside user-selected PDF regions.

    This intentionally does not perform OCR and does not match profile rows yet.
    It only converts vector PDF text into an Excel-like Contents/Position shape.
    """
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF(fitz)가 설치되어 있어야 벡터 PDF 텍스트를 추출할 수 있습니다.") from exc

    page_regions = region_config.get("page_regions") or {}
    if not page_regions:
        default_region = region_config.get("default_region")
        if default_region is not None:
            page_regions = {
                page: default_region
                for page in range(region_config["page_start"], region_config["page_end"] + 1)
            }

    if not page_regions:
        raise ValueError("PDF 선택 영역이 없습니다.")

    items = []
    log_func(f"[PDF] 파일 열기 성공: {file_path}")
    log_func(f"[PDF] 처리 페이지: {region_config['page_start']} ~ {region_config['page_end']}")
    mode_label = "모든 페이지 동일 좌표" if region_config.get("mode") == "all_pages" else "페이지별 개별 좌표"
    log_func(f"[PDF] 좌표 적용 방식: {mode_label}")

    with fitz.open(file_path) as doc:
        for page_number in sorted(page_regions):
            if page_number < 1 or page_number > doc.page_count:
                log_func(f"[PDF][WARN] {page_number}페이지는 PDF 범위를 벗어나 건너뜁니다.")
                continue

            page = doc.load_page(page_number - 1)
            user_region = _normalize_region(page_regions[page_number])
            region = expand_pdf_region(user_region, page.rect.width, page.rect.height)
            log_func(
                "[PDF] "
                f"{page_number}페이지 사용자 선택 영역: "
                f"x0={user_region[0]:.2f}, y0={user_region[1]:.2f}, "
                f"x1={user_region[2]:.2f}, y1={user_region[3]:.2f}"
            )
            log_func(
                "[PDF] "
                f"{page_number}페이지 실제 추출 영역: "
                f"x0={region[0]:.2f}, y0={region[1]:.2f}, x1={region[2]:.2f}, y1={region[3]:.2f}"
            )
            clip = fitz.Rect(*region)

            page_items = _extract_page_items(page, page_number, clip)
            items.extend(page_items)
            log_func(f"[PDF] {page_number}페이지 텍스트 객체 {len(page_items)}개 추출")

            if page_items:
                preview = ", ".join(item.contents for item in page_items[:30])
                suffix = " ..." if len(page_items) > 30 else ""
                log_func(f"[PDF][DEBUG] {page_number}페이지 텍스트 목록: {preview}{suffix}")
            else:
                log_func(f"[PDF][WARN] {page_number}페이지 선택 영역에서 벡터 텍스트를 찾지 못했습니다.")

    df = pd.DataFrame([item.to_excel_like_record() for item in items])
    log_func(f"[PDF] 선택 영역 텍스트 추출 완료: 총 {len(items)}개")
    return df, [item.to_record() for item in items]


def extract_pdf_page_region_text(file_path, page_number, region, log_func=None):
    """Extract one page region with the same padding used by full extraction."""
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF(fitz)가 설치되어 있어야 벡터 PDF 텍스트를 추출할 수 있습니다.") from exc

    with fitz.open(file_path) as doc:
        if page_number < 1 or page_number > doc.page_count:
            raise ValueError(f"{page_number}페이지는 PDF 범위를 벗어납니다.")
        page = doc.load_page(page_number - 1)
        user_region = _normalize_region(region)
        extract_region = expand_pdf_region(user_region, page.rect.width, page.rect.height)
        if log_func is not None:
            log_func(
                f"[PDF] {page_number}페이지 영역 검사 - 사용자 선택: "
                f"x0={user_region[0]:.2f}, y0={user_region[1]:.2f}, "
                f"x1={user_region[2]:.2f}, y1={user_region[3]:.2f}"
            )
            log_func(
                f"[PDF] {page_number}페이지 영역 검사 - 실제 추출: "
                f"x0={extract_region[0]:.2f}, y0={extract_region[1]:.2f}, "
                f"x1={extract_region[2]:.2f}, y1={extract_region[3]:.2f}"
            )
        items = _extract_page_items(page, page_number, fitz.Rect(*extract_region))
        df = pd.DataFrame([item.to_excel_like_record() for item in items])
        return df, [item.to_record() for item in items], extract_region


def expand_pdf_region(region, page_width, page_height):
    x0, y0, x1, y1 = _normalize_region(region)
    return (
        max(0.0, x0 - PDF_REGION_PAD_LEFT),
        max(0.0, y0 - PDF_REGION_PAD_TOP),
        min(float(page_width), x1 + PDF_REGION_PAD_RIGHT),
        min(float(page_height), y1 + PDF_REGION_PAD_BOTTOM),
    )


def analyze_pdf_label_rows(
    text_items,
    log_func,
    pdf_y_tolerance=PDF_Y_TOLERANCE,
    pdf_x_tolerance=PDF_X_TOLERANCE,
    row_cluster_tolerance=PDF_ROW_CLUSTER_TOLERANCE,
):
    """Find distance/elevation label rows and collect numeric values near them.

    This only finds rows. It intentionally does not match distance/elevation by X.
    """
    items = [_coerce_item(item) for item in text_items]
    if not items:
        log_func("[PDF][WARN] 라벨 분석할 텍스트 객체가 없습니다.")
        return {}

    log_func(
        "[PDF] 라벨 행 분석 시작: "
        f"pdf_y_tolerance={pdf_y_tolerance}, pdf_x_tolerance={pdf_x_tolerance}, "
        f"row_cluster_tolerance={row_cluster_tolerance}"
    )

    result = {}
    for page in sorted({item.page for item in items}):
        page_items = [item for item in items if item.page == page]
        distance_labels = _find_distance_labels(page_items, pdf_y_tolerance, pdf_x_tolerance)
        elevation_labels = _find_exact_labels(page_items, "관저고", "관저고")

        log_func(f"[PDF][DEBUG] {page}페이지 라벨 분석 대상 텍스트 {len(page_items)}개")
        _log_labels(log_func, page, "누가거리", distance_labels)
        _log_labels(log_func, page, "관저고", elevation_labels)

        number_rows = _cluster_number_rows(page_items, row_cluster_tolerance)
        log_func(f"[PDF][DEBUG] {page}페이지 숫자 행 클러스터 {len(number_rows)}개 감지")
        for row in number_rows:
            log_func(
                "[PDF][DEBUG] 숫자 행 클러스터: "
                f"y={row['y']:.2f}, count={row['count']}, "
                f"min={row['min']:.2f}, max={row['max']:.2f}, "
                f"monotonic_score={row['monotonic_score']:.2f}"
            )

        distance_label = distance_labels[0] if distance_labels else None
        elevation_label = elevation_labels[0] if elevation_labels else None

        if distance_label is None:
            log_func(f"[PDF][WARN] {page}페이지 누가거리 라벨을 찾지 못했습니다.")
        if elevation_label is None:
            log_func(f"[PDF][WARN] {page}페이지 관저고 라벨을 찾지 못했습니다.")

        distance_row = _select_distance_row(number_rows, distance_label, pdf_y_tolerance, log_func, page)
        elevation_row = _select_elevation_row(number_rows, elevation_label, pdf_y_tolerance, log_func, page)
        distance_numbers = distance_row["items"] if distance_row is not None else []
        elevation_numbers = elevation_row["items"] if elevation_row is not None else []

        log_func(f"[PDF] {page}페이지 누가거리 행 숫자 {len(distance_numbers)}개 발견")
        _log_numbers(log_func, page, "누가거리", distance_numbers)
        log_func(f"[PDF] {page}페이지 관저고 행 숫자 {len(elevation_numbers)}개 발견")
        _log_numbers(log_func, page, "관저고", elevation_numbers)

        result[page] = {
            "distance_label": _label_to_record(distance_label),
            "elevation_label": _label_to_record(elevation_label),
            "distance_row_y": distance_row["y"] if distance_row is not None else None,
            "elevation_row_y": elevation_row["y"] if elevation_row is not None else None,
            "number_rows": [_row_to_record(row) for row in number_rows],
            "selected_distance_row_y": distance_row["y"] if distance_row is not None else None,
            "selected_elevation_row_y": elevation_row["y"] if elevation_row is not None else None,
            "distance_numbers": [_item_to_number_record(item) for item in distance_numbers],
            "elevation_numbers": [_item_to_number_record(item) for item in elevation_numbers],
        }

    return result


def match_pdf_profile_rows(
    label_rows,
    log_func,
    pdf_x_tolerance=PDF_X_TOLERANCE,
):
    """Match distance/elevation row numbers by nearest X coordinate.

    Returns a read-only preview DataFrame. It does not connect to graph/save flow.
    """
    records = []
    if not label_rows:
        log_func("[PDF][ERROR] 매칭할 라벨 행 분석 결과가 없습니다.")
        return _profile_dataframe(records)

    log_func(f"[PDF] X좌표 매칭 시작: pdf_x_tolerance={pdf_x_tolerance}")

    for page in sorted(label_rows):
        page_rows = label_rows[page]
        distance_numbers = list(page_rows.get("distance_numbers") or [])
        elevation_numbers = list(page_rows.get("elevation_numbers") or [])
        distance_label = page_rows.get("distance_label")
        elevation_label = page_rows.get("elevation_label")

        if distance_label is None:
            log_func(f"[PDF][ERROR] {page}페이지 누가거리 라벨 미검출")
        if elevation_label is None:
            log_func(f"[PDF][ERROR] {page}페이지 관저고 라벨 미검출")
        if not distance_numbers:
            log_func(f"[PDF][ERROR] {page}페이지 누가거리 숫자 부족")
        if not elevation_numbers:
            log_func(f"[PDF][ERROR] {page}페이지 관저고 숫자 부족")

        used_elevation_indexes = set()
        previous_distance = None
        line_id = 1
        line_counts = {line_id: 0}
        matched_count = 0

        for distance in distance_numbers:
            status = []
            distance_value = _parse_number(distance["contents"])
            if distance_value is None:
                status.append("누가거리 숫자 변환 실패")

            if previous_distance is not None and distance_value is not None:
                if _is_new_profile_line(previous_distance, distance_value):
                    log_func(
                        "[PDF] 라인 분리 감지: "
                        f"페이지 {page}, line_id {line_id} -> {line_id + 1}, "
                        f"누가거리 {previous_distance:g} -> {distance_value:g}"
                    )
                    line_id += 1
                    line_counts[line_id] = 0
                elif distance_value <= previous_distance:
                    status.append("누가거리 증가 검증 실패")
                    log_func(
                        "[PDF][WARN] 누가거리 값이 증가하지 않습니다. "
                        f"페이지 {page}, 값: {previous_distance:g} -> {distance_value:g}"
                    )
            if distance_value is not None:
                previous_distance = distance_value
            line_counts[line_id] = line_counts.get(line_id, 0) + 1

            nearest_index = None
            nearest_elevation = None
            nearest_x_diff = None
            for index, elevation in enumerate(elevation_numbers):
                if index in used_elevation_indexes:
                    continue
                x_diff = abs(float(elevation["x"]) - float(distance["x"]))
                if nearest_x_diff is None or x_diff < nearest_x_diff:
                    nearest_index = index
                    nearest_elevation = elevation
                    nearest_x_diff = x_diff

            elevation_value = None
            if nearest_elevation is None:
                status.append("관저고 매칭 실패")
            elif nearest_x_diff is not None and nearest_x_diff <= pdf_x_tolerance:
                used_elevation_indexes.add(nearest_index)
                matched_count += 1
                elevation_value = _parse_number(nearest_elevation["contents"])
                if elevation_value is None:
                    status.append("관저고 숫자 변환 실패")
            else:
                status.append("관저고 X 허용오차 초과")
                log_func(
                    "[PDF][WARN] "
                    f"{page}페이지 누가거리 {distance['contents']}의 관저고 X 매칭 실패: "
                    f"누가거리 X={float(distance['x']):.2f}, "
                    f"가장 가까운 관저고 X={float(nearest_elevation['x']):.2f}, "
                    f"차이={nearest_x_diff:.2f}"
                )

            records.append(
                {
                    "line_id": line_id,
                    "페이지": page,
                    "누가거리": _format_distance(distance_value),
                    "관저고": _format_elevation(elevation_value),
                    "누가거리 X": _format_coord(distance["x"]),
                    "관저고 X": _format_coord(nearest_elevation["x"]) if nearest_elevation else "-",
                    "X오차": _format_coord(nearest_x_diff) if nearest_x_diff is not None else "-",
                    "원본 누가거리": distance["contents"],
                    "원본 관저고": nearest_elevation["contents"] if nearest_elevation else "-",
                    "상태": "정상" if not status else " / ".join(status),
                }
            )

        extra_elevations = len(elevation_numbers) - len(used_elevation_indexes)
        if extra_elevations > 0 and distance_numbers:
            log_func(f"[PDF][WARN] {page}페이지 미사용 관저고 숫자 {extra_elevations}개")

        if distance_numbers and elevation_numbers and matched_count != len(distance_numbers):
            log_func(
                "[PDF][WARN] "
                f"{page}페이지 누가거리/관저고 매칭 개수 불일치: "
                f"누가거리 {len(distance_numbers)}개, 관저고 {len(elevation_numbers)}개, 성공 {matched_count}개"
            )
        elif distance_numbers and elevation_numbers:
            log_func(f"[PDF] {page}페이지 X좌표 매칭 성공: {matched_count}개")
        log_func(
            "[PDF] 라인 분리 결과: "
            + ", ".join(f"line_id {line}: {count}개" for line, count in sorted(line_counts.items()))
        )

    df = _profile_dataframe(records)
    ok_count = int((df["상태"] == "정상").sum()) if not df.empty else 0
    warn_count = int(len(df) - ok_count)
    log_func(f"[PDF] X좌표 매칭 완료: 정상 {ok_count}개 / 경고 {warn_count}개")
    return df


def _extract_page_items(page, page_number, clip):
    raw = page.get_text("dict", clip=clip)
    items = []

    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            rotation = _line_rotation(line)
            for span in line.get("spans", []):
                text = str(span.get("text", "")).strip()
                if not text:
                    continue
                bbox = _normalize_region(span.get("bbox", (0, 0, 0, 0)))
                center_x = round((bbox[0] + bbox[2]) / 2, 2)
                center_y = round((bbox[1] + bbox[3]) / 2, 2)
                items.append(
                    PdfTextItem(
                        page=page_number,
                        contents=text,
                        x=center_x,
                        y=center_y,
                        bbox=tuple(round(v, 2) for v in bbox),
                        rotation=rotation,
                    )
                )

    items.sort(key=lambda item: (item.page, item.y, item.x))
    return items


def _cluster_number_rows(items, tolerance):
    number_items = [item for item in items if _is_number_text(item.contents)]
    number_items.sort(key=lambda item: item.y)
    rows = []

    for item in number_items:
        if not rows or abs(rows[-1]["items"][-1].y - item.y) > tolerance:
            rows.append({"items": [item]})
        else:
            rows[-1]["items"].append(item)

    enriched = []
    for row in rows:
        row_items = sorted(row["items"], key=lambda item: item.x)
        values = [_parse_number(item.contents) for item in row_items]
        values = [value for value in values if value is not None]
        if not values:
            continue
        y = sum(item.y for item in row_items) / len(row_items)
        monotonic_score = _monotonic_score(values)
        enriched.append(
            {
                "y": round(y, 2),
                "items": row_items,
                "count": len(row_items),
                "min": min(values),
                "max": max(values),
                "range": max(values) - min(values),
                "monotonic_score": monotonic_score,
                "values": values,
            }
        )
    return enriched


def _select_distance_row(number_rows, label, y_tolerance, log_func, page):
    if label is None:
        return None
    search_window = max(y_tolerance * 2.5, PDF_ROW_CLUSTER_TOLERANCE * 6)
    label_y = label["y"] if isinstance(label, dict) else label.y
    candidates = [row for row in number_rows if abs(row["y"] - label_y) <= search_window]
    if not candidates:
        log_func(f"[PDF][WARN] {page}페이지 누가거리 라벨 근처 숫자 행을 찾지 못했습니다.")
        return None

    max_range = max(row["range"] for row in candidates) or 1.0
    max_count = max(row["count"] for row in candidates) or 1
    for row in candidates:
        row["distance_score"] = (
            row["monotonic_score"] * 0.65
            + (row["range"] / max_range) * 0.25
            + (row["count"] / max_count) * 0.10
        )

    selected = max(candidates, key=lambda row: (row["distance_score"], row["monotonic_score"], row["range"], row["count"]))
    for row in sorted(candidates, key=lambda item: item["y"]):
        is_selected = row is selected
        log_func(
            "[PDF][DEBUG] 누가거리 후보 행: "
            f"y={row['y']:.2f}, count={row['count']}, max={row['max']:.2f}, "
            f"monotonic_score={row['monotonic_score']:.2f}, selected={is_selected}"
        )
        if not is_selected:
            reason = "구간거리형 행으로 판단" if row["monotonic_score"] < selected["monotonic_score"] else "누적거리 점수 낮음"
            log_func(f"[PDF][DEBUG] 누가거리 후보 행 제외: y={row['y']:.2f}, reason={reason}")
    log_func(f"[PDF] 누가거리 선택 행: y={selected['y']:.2f}, count={selected['count']}")
    return selected


def _select_elevation_row(number_rows, label, y_tolerance, log_func, page):
    if label is None:
        return None
    label_y = label["y"] if isinstance(label, dict) else label.y
    search_window = max(y_tolerance * 2.5, PDF_ROW_CLUSTER_TOLERANCE * 6)
    candidates = [row for row in number_rows if abs(row["y"] - label_y) <= search_window]
    if not candidates:
        log_func(f"[PDF][WARN] {page}페이지 관저고 라벨 근처 숫자 행을 찾지 못했습니다.")
        return None

    candidates = sorted(candidates, key=lambda row: row["y"])
    if len(candidates) >= 3:
        selected = candidates[len(candidates) // 2]
    else:
        selected = min(candidates, key=lambda row: abs(row["y"] - label_y))

    for index, row in enumerate(candidates):
        is_selected = row is selected
        reason = ""
        if not is_selected:
            if len(candidates) >= 3:
                reason = "토피 행으로 판단" if index < candidates.index(selected) else "지반고 행으로 판단"
            else:
                reason = "관저고 라벨 중심 Y에서 더 먼 행"
        log_func(
            "[PDF][DEBUG] 관저고 후보 행: "
            f"y={row['y']:.2f}, count={row['count']}, selected={is_selected}"
            + (f", reason={reason}" if reason else "")
        )
    log_func(f"[PDF] 관저고 선택 행: y={selected['y']:.2f}, count={selected['count']}")
    return selected


def _monotonic_score(values):
    if len(values) <= 1:
        return 1.0 if values else 0.0
    increases = 0
    comparisons = 0
    for previous, current in zip(values, values[1:]):
        comparisons += 1
        if current >= previous:
            increases += 1
    return increases / comparisons if comparisons else 0.0


def _find_exact_labels(items, needle, name):
    labels = []
    normalized_needle = _normalize_text(needle)
    for item in items:
        if normalized_needle in _normalize_text(item.contents):
            labels.append(
                PdfLabel(
                    page=item.page,
                    name=name,
                    x=item.x,
                    y=item.y,
                    contents=item.contents,
                    source="exact",
                )
            )
    labels.sort(key=lambda label: (label.y, label.x))
    return labels


def _find_distance_labels(items, y_tolerance, x_tolerance):
    labels = _find_exact_labels(items, "누가거리", "누가거리")
    labels.extend(_find_split_distance_labels(items, y_tolerance, x_tolerance))
    labels.sort(key=lambda label: (label.y, label.x, label.source))
    return labels


def _find_split_distance_labels(items, y_tolerance, x_tolerance):
    nu_items = [item for item in items if _normalize_text(item.contents) == "누가"]
    distance_items = [item for item in items if _normalize_text(item.contents) == "거리"]
    labels = []
    max_x_gap = max(x_tolerance * 6, 30.0)

    for nu_item in nu_items:
        candidates = [
            distance_item
            for distance_item in distance_items
            if abs(distance_item.y - nu_item.y) <= y_tolerance
            and 0 <= distance_item.x - nu_item.x <= max_x_gap
        ]
        if not candidates:
            continue
        nearest = min(candidates, key=lambda item: abs(item.x - nu_item.x))
        labels.append(
            PdfLabel(
                page=nu_item.page,
                name="누가거리",
                x=round((nu_item.x + nearest.x) / 2, 2),
                y=round((nu_item.y + nearest.y) / 2, 2),
                contents=f"{nu_item.contents}+{nearest.contents}",
                source="split",
            )
        )
    return labels


def _collect_row_numbers(items, label, y_tolerance):
    if label is None:
        return []
    numbers = [
        item
        for item in items
        if abs(item.y - label.y) <= y_tolerance
        and _is_number_text(item.contents)
    ]
    numbers.sort(key=lambda item: item.x)
    return numbers


def _is_number_text(text):
    cleaned = str(text).strip().replace(",", "").replace(" ", "")
    return bool(re.fullmatch(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)", cleaned))


def _normalize_text(text):
    return re.sub(r"\s+", "", str(text).strip())


def _coerce_item(item):
    if isinstance(item, PdfTextItem):
        return item
    return PdfTextItem(
        page=int(item["page"]),
        contents=str(item["contents"]),
        x=float(item["x"]),
        y=float(item["y"]),
        bbox=tuple(float(value) for value in item["bbox"]),
        rotation=int(item.get("rotation", 0)),
    )


def _label_to_record(label):
    if label is None:
        return None
    return {
        "page": label.page,
        "name": label.name,
        "x": label.x,
        "y": label.y,
        "contents": label.contents,
        "source": label.source,
    }


def _item_to_number_record(item):
    return {
        "page": item.page,
        "contents": item.contents,
        "x": item.x,
        "y": item.y,
        "bbox": item.bbox,
        "rotation": item.rotation,
    }


def _row_to_record(row):
    return {
        "y": row["y"],
        "count": row["count"],
        "min": row["min"],
        "max": row["max"],
        "range": row["range"],
        "monotonic_score": row["monotonic_score"],
        "items": [_item_to_number_record(item) for item in row["items"]],
    }


def _log_labels(log_func, page, name, labels):
    log_func(f"[PDF] {page}페이지 {name} 라벨 후보 {len(labels)}개 발견")
    for label in labels[:10]:
        log_func(
            f"[PDF] {name} 라벨 인식: contents='{label.contents}', "
            f"x={label.x:.2f}, y={label.y:.2f}"
        )
        log_func(
            "[PDF][DEBUG] "
            f"{page}페이지 {name} 라벨: "
            f"source={label.source}, text={label.contents}, x={label.x:.2f}, y={label.y:.2f}"
        )


def _log_numbers(log_func, page, row_name, numbers):
    if not numbers:
        log_func(f"[PDF][DEBUG] {page}페이지 {row_name} 행 숫자 없음")
        return
    preview = ", ".join(
        f"{item.contents}(x={item.x:.2f}, y={item.y:.2f})"
        for item in numbers[:30]
    )
    suffix = " ..." if len(numbers) > 30 else ""
    log_func(f"[PDF][DEBUG] {page}페이지 {row_name} 행 숫자: {preview}{suffix}")


def _parse_number(value):
    cleaned = str(value).strip().replace(",", "").replace(" ", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _is_new_profile_line(previous, current):
    if current >= previous:
        return False
    drop = previous - current
    return drop >= max(20.0, previous * 0.25)


def _format_distance(value):
    if value is None:
        return "-"
    return f"{value:.2f}"


def _format_elevation(value):
    if value is None:
        return "-"
    return f"{value:.2f}"


def _format_coord(value):
    return f"{float(value):.2f}"


def _profile_dataframe(records):
    columns = [
        "line_id",
        "페이지",
        "누가거리",
        "관저고",
        "누가거리 X",
        "관저고 X",
        "X오차",
        "원본 누가거리",
        "원본 관저고",
        "상태",
    ]
    return pd.DataFrame(records, columns=columns)


def _line_rotation(line):
    direction = line.get("dir")
    if not direction or len(direction) < 2:
        return 0
    angle = math.degrees(math.atan2(direction[1], direction[0]))
    normalized = int(round(angle / 90.0) * 90) % 360
    return normalized


def _normalize_region(region):
    x0, y0, x1, y1 = [float(value) for value in region]
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)

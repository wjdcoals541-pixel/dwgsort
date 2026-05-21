from __future__ import annotations

import math
import re
from dataclasses import dataclass

import pandas as pd

from .config import PDF_X_TOLERANCE, PDF_Y_TOLERANCE


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

            region = _normalize_region(page_regions[page_number])
            clip = fitz.Rect(*region)
            page = doc.load_page(page_number - 1)
            log_func(
                "[PDF] "
                f"{page_number}페이지 선택 영역: "
                f"x0={region[0]:.2f}, y0={region[1]:.2f}, x1={region[2]:.2f}, y1={region[3]:.2f}"
            )

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


def analyze_pdf_label_rows(
    text_items,
    log_func,
    pdf_y_tolerance=PDF_Y_TOLERANCE,
    pdf_x_tolerance=PDF_X_TOLERANCE,
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
        f"pdf_y_tolerance={pdf_y_tolerance}, pdf_x_tolerance={pdf_x_tolerance}"
    )

    result = {}
    for page in sorted({item.page for item in items}):
        page_items = [item for item in items if item.page == page]
        distance_labels = _find_distance_labels(page_items, pdf_y_tolerance, pdf_x_tolerance)
        elevation_labels = _find_exact_labels(page_items, "관저고", "관저고")

        log_func(f"[PDF][DEBUG] {page}페이지 라벨 분석 대상 텍스트 {len(page_items)}개")
        _log_labels(log_func, page, "누가거리", distance_labels)
        _log_labels(log_func, page, "관저고", elevation_labels)

        distance_label = distance_labels[0] if distance_labels else None
        elevation_label = elevation_labels[0] if elevation_labels else None

        if distance_label is None:
            log_func(f"[PDF][WARN] {page}페이지 누가거리 라벨을 찾지 못했습니다.")
        if elevation_label is None:
            log_func(f"[PDF][WARN] {page}페이지 관저고 라벨을 찾지 못했습니다.")

        distance_numbers = _collect_row_numbers(page_items, distance_label, pdf_y_tolerance)
        elevation_numbers = _collect_row_numbers(page_items, elevation_label, pdf_y_tolerance)

        log_func(f"[PDF] {page}페이지 누가거리 행 숫자 {len(distance_numbers)}개 발견")
        _log_numbers(log_func, page, "누가거리", distance_numbers)
        log_func(f"[PDF] {page}페이지 관저고 행 숫자 {len(elevation_numbers)}개 발견")
        _log_numbers(log_func, page, "관저고", elevation_numbers)

        result[page] = {
            "distance_label": _label_to_record(distance_label),
            "elevation_label": _label_to_record(elevation_label),
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
        matched_count = 0

        for distance in distance_numbers:
            status = []
            distance_value = _parse_number(distance["contents"])
            if distance_value is None:
                status.append("누가거리 숫자 변환 실패")

            if previous_distance is not None and distance_value is not None:
                if distance_value <= previous_distance:
                    status.append("누가거리 증가 검증 실패")
                    log_func(
                        "[PDF][WARN] 누가거리 값이 증가하지 않습니다. "
                        f"페이지 {page}, 값: {previous_distance:g} -> {distance_value:g}"
                    )
            if distance_value is not None:
                previous_distance = distance_value

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
                    "페이지": page,
                    "누가거리": _format_distance(distance_value),
                    "관저고": _format_elevation(elevation_value),
                    "누가거리 X": _format_coord(distance["x"]),
                    "관저고 X": _format_coord(nearest_elevation["x"]) if nearest_elevation else "-",
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


def _log_labels(log_func, page, name, labels):
    log_func(f"[PDF] {page}페이지 {name} 라벨 후보 {len(labels)}개 발견")
    for label in labels[:10]:
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
        "페이지",
        "누가거리",
        "관저고",
        "누가거리 X",
        "관저고 X",
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

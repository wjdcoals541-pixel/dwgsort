from __future__ import annotations

import pandas as pd

from .config import PDF_ROW_CLUSTER_TOLERANCE, PDF_X_TOLERANCE, PDF_Y_TOLERANCE
from .pdf_vector_parser import (
    PdfTextItem,
    analyze_pdf_label_rows,
    match_pdf_profile_rows,
)


def extract_dxf_text(file_path, log_func):
    """Extract text-like entities from a DXF modelspace."""
    try:
        import ezdxf
    except ImportError as exc:
        raise RuntimeError("DXF 처리를 위해 ezdxf가 필요합니다. requirements.txt 설치를 확인하세요.") from exc

    doc = ezdxf.readfile(file_path)
    modelspace = doc.modelspace()
    items = []

    for entity in modelspace:
        kind = entity.dxftype()
        if kind not in {"TEXT", "MTEXT", "ATTRIB", "ATTDEF"}:
            continue

        text = _entity_text(entity, kind)
        if not str(text).strip():
            continue

        insert = getattr(entity.dxf, "insert", None)
        if insert is None:
            continue

        x = float(insert.x)
        y = float(insert.y)
        rotation = int(round(float(getattr(entity.dxf, "rotation", 0) or 0)))
        items.append(
            PdfTextItem(
                page=1,
                contents=str(text).strip(),
                x=x,
                y=y,
                bbox=(x, y, x, y),
                rotation=rotation,
            )
        )

    df = pd.DataFrame([_to_excel_like_record(item) for item in items])
    if df.empty:
        df = pd.DataFrame(
            columns=["DXF페이지", "Contents", "Position", "X", "Y", "BBox", "Rotation"]
        )

    log_func(f"[DXF] 텍스트 객체 {len(items)}개 추출")
    if items:
        preview = ", ".join(item.contents for item in items[:30])
        suffix = " ..." if len(items) > 30 else ""
        log_func(f"[DXF][DEBUG] 텍스트 목록: {preview}{suffix}")
    return df, items


def process_dxf_profile(
    file_path,
    log_func,
    y_tolerance=PDF_Y_TOLERANCE,
    x_tolerance=PDF_X_TOLERANCE,
    row_cluster_tolerance=PDF_ROW_CLUSTER_TOLERANCE,
):
    text_df, items = extract_dxf_text(file_path, log_func)
    if not items:
        return text_df, pd.DataFrame()

    log_func(
        "[DXF] 설정: "
        f"y_tolerance={y_tolerance}, "
        f"x_tolerance={x_tolerance}, "
        f"row_cluster_tolerance={row_cluster_tolerance}"
    )
    label_rows = analyze_pdf_label_rows(
        items,
        log_func,
        pdf_y_tolerance=y_tolerance,
        pdf_x_tolerance=x_tolerance,
        row_cluster_tolerance=row_cluster_tolerance,
    )
    profile_df = match_pdf_profile_rows(
        label_rows,
        log_func,
        pdf_x_tolerance=x_tolerance,
    )
    return text_df, profile_df


def _entity_text(entity, kind):
    if kind == "MTEXT":
        try:
            return entity.plain_text()
        except Exception:
            return entity.text
    return getattr(entity.dxf, "text", "")


def _to_excel_like_record(item):
    return {
        "DXF페이지": item.page,
        "Contents": item.contents,
        "Position": item.position,
        "X": item.x,
        "Y": item.y,
        "BBox": item.bbox,
        "Rotation": item.rotation,
    }

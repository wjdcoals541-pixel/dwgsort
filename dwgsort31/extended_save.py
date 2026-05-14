import pandas as pd

from .excel_compat import add_result_column
from .utils import safe_output_path


def ensure_extended_columns(df):
    result_df = add_result_column(df)
    defaults = {
        "라인명": "Excel",
        "도면번호": "",
        "PDF페이지": "",
        "측점": "",
        "단거리": "",
        "지반고": "",
        "토피": "",
        "confidence": "",
        "source_text": "",
        "row_tokens": "",
        "profile_title": "",
    }
    for col, default in defaults.items():
        if col not in result_df.columns:
            result_df[col] = default
    return result_df


def save_extended_31_excel(raw_df, filtered_df, output_path):
    raw_df = ensure_extended_columns(raw_df)
    filtered_df = ensure_extended_columns(filtered_df)
    safe_path = safe_output_path(output_path)

    preferred_cols = [
        "라인명",
        "도면번호",
        "PDF페이지",
        "profile_title",
        "측점",
        "단거리",
        "누가거리",
        "지반고",
        "관저고",
        "토피",
        "결과",
        "confidence",
        "source_text",
        "row_tokens",
    ]
    raw_cols = [c for c in preferred_cols if c in raw_df.columns] + [
        c for c in raw_df.columns if c not in preferred_cols
    ]
    filtered_cols = [c for c in preferred_cols if c in filtered_df.columns] + [
        c for c in filtered_df.columns if c not in preferred_cols
    ]

    with pd.ExcelWriter(safe_path, engine="openpyxl") as writer:
        raw_df[raw_cols].to_excel(writer, sheet_name="Raw", index=False)
        filtered_df[filtered_cols].to_excel(writer, sheet_name="Filtered", index=False)

    return safe_path

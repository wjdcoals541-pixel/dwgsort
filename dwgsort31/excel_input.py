"""Normalize CAD extraction columns and read numeric profile layers."""

import math

import pandas as pd

from .config import DISTANCE_LABELS


def read_excel_extraction(file_path, log_func):
    frames = []
    aliases = {
        "Contents": ("contents", "컨텐츠", "콘텐츠", "내용"),
        "Position": ("position", "위치"),
        "Layer": ("layer", "도면층"),
    }
    for sheet, frame in pd.read_excel(file_path, sheet_name=None).items():
        if frame.empty:
            continue
        columns = {str(col).strip().casefold(): col for col in frame.columns}
        normalized = frame.copy()
        for target, names in aliases.items():
            sources = [columns[name] for name in names if name in columns]
            if sources:
                values = frame[sources].replace(r"^\s*$", pd.NA, regex=True)
                normalized[target] = values.bfill(axis=1).iloc[:, 0]
                log_func(f"[Excel] {sheet}: {', '.join(map(str, sources))} → {target}")
        if "position: x" in columns and "position: y" in columns:
            x = frame[columns["position: x"]]
            y = frame[columns["position: y"]]
            separate = x.astype(str) + "," + y.astype(str)
            if "Position" in normalized:
                normalized["Position"] = normalized["Position"].fillna(separate)
            else:
                normalized["Position"] = separate
                log_func(f"[Excel] {sheet}: Position: X/Y → Position")
        if not {"Contents", "Position"}.issubset(normalized.columns):
            log_func(f"[Excel] {sheet}: 문자 내용 또는 위치 열이 없어 건너뜁니다.")
            continue
        normalized["_sheet"] = sheet
        frames.append(normalized)
    if not frames:
        raise ValueError(
            "문자 내용(Contents/컨텐츠)과 위치(Position/위치 또는 Position: X·Y) 열이 필요합니다."
        )
    return pd.concat(frames, ignore_index=True)


def extract_layer_profiles(df, log_func, tolerance):
    """Use explicit profile layers only when text labels are absent.

    Distance and elevation values stay unchanged. X order and distance resets
    identify separate profiles, so equal chainages on different lines survive.
    """
    if "Layer" not in df:
        return None
    records = []
    line_id = 0
    for sheet, sheet_df in df.groupby("_sheet", sort=False):
        sheet_df = sheet_df.copy()
        sheet_df["_layer"] = sheet_df["Layer"].astype(str).str.strip()
        sheet_df["_value"] = pd.to_numeric(
            sheet_df["Contents_clean"].str.replace(",", "", regex=False), errors="coerce"
        )
        numeric = sheet_df[sheet_df["_value"].map(lambda v: pd.notna(v) and math.isfinite(v))]
        distances = numeric[numeric["_layer"].isin(DISTANCE_LABELS)]
        if distances.empty:
            continue
        elevation_layer = next(
            (name for name in ("관저고박스", "관저고", "관저고원") if numeric["_layer"].eq(name).any()),
            None,
        )
        if elevation_layer is None:
            raise ValueError(f"{sheet}: 거리 도면층은 있지만 관저고 도면층이 없습니다.")
        elevations = numeric[numeric["_layer"].eq(elevation_layer)]
        # Keep separate drawing rows separate; avoid chaining distant rows.
        bands = []
        for _, row in distances.sort_values("Y", ascending=False).iterrows():
            if not bands or abs(bands[-1][0]["Y"] - row["Y"]) > tolerance:
                bands.append([])
            bands[-1].append(row)
        sheet_count = 0
        for band in bands:
            line_id += 1
            previous = None
            for distance in sorted(band, key=lambda row: row["X"]):
                value = distance["_value"]
                if previous is not None and (value < previous or value == previous == 0):
                    line_id += 1
                previous = value
                candidates = elevations.assign(
                    _dx=(elevations["X"] - distance["X"]).abs(),
                    _dy=(elevations["Y"] - distance["Y"]).abs(),
                ).sort_values(["_dx", "_dy"])
                nearest = candidates.iloc[0]
                if nearest["_dx"] > tolerance * 2.5:
                    raise ValueError(f"{sheet}: 거리 {distance['Contents_clean']}의 관저고 X 매칭 실패")
                tied = candidates[
                    candidates["_dx"].sub(nearest["_dx"]).abs().lt(1e-8)
                    & candidates["_dy"].sub(nearest["_dy"]).abs().lt(1e-8)
                ]
                if tied["_value"].nunique() > 1:
                    raise ValueError(f"{sheet}: 같은 위치에 서로 다른 관저고가 있어 확인이 필요합니다.")
                records.append({
                    "line_id": line_id,
                    "관저고": nearest["Contents_clean"],
                    "누가거리": distance["Contents_clean"],
                })
                sheet_count += 1
        log_func(f"[Excel] {sheet}: 도면층 기준 거리/{elevation_layer} {sheet_count}개 매칭")
    if not records:
        return None
    result = pd.DataFrame(records)
    log_func(f"[Excel] {result['line_id'].nunique()}개 종단, 전체 {len(result)}개 점 추출")
    return result

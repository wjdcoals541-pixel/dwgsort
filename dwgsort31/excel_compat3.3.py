import os

import pandas as pd

from .utils import safe_output_path


def extract_coordinates(pos_str):
    try:
        parts = str(pos_str).split(",")
        if len(parts) >= 2:
            return float(parts[0]), float(parts[1])
    except (TypeError, ValueError):
        pass
    return None, None


def is_numeric(val):
    try:
        float(str(val).replace(",", "").replace(" ", ""))
        return True
    except (TypeError, ValueError):
        return False


def to_float(val):
    return float(str(val).replace(",", "").replace(" ", ""))


def get_y_clusters(y_series, tol):
    """Group nearby Y coordinates into drawing tiers."""
    if y_series.empty:
        return []

    sorted_y = sorted(y_series.tolist(), reverse=True)
    clusters = []
    current_cluster = [sorted_y[0]]

    for y in sorted_y[1:]:
        if abs(current_cluster[-1] - y) <= tol:
            current_cluster.append(y)
        else:
            clusters.append(sum(current_cluster) / len(current_cluster))
            current_cluster = [y]

    if current_cluster:
        clusters.append(sum(current_cluster) / len(current_cluster))
    return clusters


def process_excel_data(file_path, log_func, tolerance):
    """2.4-compatible Excel coordinate extraction."""
    log_func(f"\n⏳ 읽는 중: {os.path.basename(file_path)}")
    try:
        xls = pd.read_excel(file_path, sheet_name=None)
        master_df = pd.concat(xls.values(), ignore_index=True)
    except Exception as e:
        log_func(f" ❌ 파일 읽기 오류: {e}")
        return None

    if "Contents" not in master_df.columns or "Position" not in master_df.columns:
        log_func(" ❌ 필수 열('Contents', 'Position')이 없습니다.")
        return None

    master_df["Contents_clean"] = master_df["Contents"].astype(str).str.strip()
    master_df[["X", "Y"]] = master_df["Position"].apply(
        lambda x: pd.Series(extract_coordinates(x))
    )
    df = master_df.dropna(subset=["X", "Y"]).copy()

    nu_rows = df[df["Contents_clean"] == "누가거리"]
    gwan_rows = df[df["Contents_clean"] == "관저고"]

    if nu_rows.empty or gwan_rows.empty:
        log_func(" ⚠️ '누가거리' 또는 '관저고' 텍스트를 찾을 수 없습니다.")
        return None

    nu_y_clusters = get_y_clusters(nu_rows["Y"], tolerance)
    gwan_y_clusters = get_y_clusters(gwan_rows["Y"], tolerance)
    tier_count = min(len(nu_y_clusters), len(gwan_y_clusters))
    log_func(f"  -> 도면 분석 완료: 총 {tier_count}개의 단(줄)을 발견했습니다.")

    numeric_df = df[
        (df["Contents_clean"] != "누가거리")
        & (df["Contents_clean"] != "관저고")
        & (df["Contents_clean"].apply(is_numeric))
    ].copy()
    numeric_df["Value_num"] = numeric_df["Contents_clean"].apply(to_float)

    all_matched = []
    for i in range(tier_count):
        ref_y_nu = nu_y_clusters[i]
        ref_y_gwan = gwan_y_clusters[i]

        nu_cands = numeric_df[abs(numeric_df["Y"] - ref_y_nu) <= tolerance]
        gwan_cands = numeric_df[abs(numeric_df["Y"] - ref_y_gwan) <= tolerance]

        for _, nu_row in nu_cands.iterrows():
            if gwan_cands.empty:
                break

            x_nu = nu_row["X"]
            gwan_cands_copy = gwan_cands.copy()
            gwan_cands_copy["X_diff"] = abs(gwan_cands_copy["X"] - x_nu)
            nearest_gwan = gwan_cands_copy.loc[gwan_cands_copy["X_diff"].idxmin()]

            if nearest_gwan["X_diff"] <= tolerance * 2.5:
                all_matched.append(
                    {
                        "관저고": nearest_gwan["Contents_clean"],
                        "누가거리": nu_row["Contents_clean"],
                        "누가거리_num": nu_row["Value_num"],
                    }
                )

    if not all_matched:
        log_func(" ⚠️ 매칭된 숫자 데이터를 찾지 못했습니다.")
        return None

    matched_df = pd.DataFrame(all_matched)
    matched_df = (
        matched_df.sort_values(by="누가거리_num")
        .drop_duplicates(subset=["누가거리_num"])
        .reset_index(drop=True)
    )

    log_func(f"  -> 데이터 병합 완료: 총 {len(matched_df)}개 좌표 추출 (중복 제거됨)")
    return matched_df[["관저고", "누가거리"]]


def filter_graph_points_24(
    df,
    log_func,
    slope_threshold,
    max_dist,
    peak_prominence=0.30,
    peak_window=2,
):
    """2.4-compatible point compression.

    Preservation priority:
    1. first/last point
    2. slope-change points, calculated from original neighboring points
    3. local peaks/valleys using only peak_prominence
    4. low-priority spacing points when important points are farther than max_dist
    """
    df = df.copy()
    df["누가거리_num"] = pd.to_numeric(
        df["누가거리"].astype(str).str.replace(",", "", regex=False),
        errors="coerce",
    )
    df["관저고_num"] = pd.to_numeric(
        df["관저고"].astype(str).str.replace(",", "", regex=False),
        errors="coerce",
    )
    df = (
        df.dropna(subset=["누가거리_num", "관저고_num"])
        .sort_values("누가거리_num")
        .drop_duplicates(subset=["누가거리_num"], keep="first")
        .reset_index(drop=True)
    )

    if len(df) <= 2:
        return df.drop(columns=["누가거리_num", "관저고_num"], errors="ignore").copy()

    n = len(df)
    x = df["누가거리_num"].tolist()
    y = df["관저고_num"].tolist()

    max_dist = max(float(max_dist or 0), 0.0)
    slope_threshold = float(slope_threshold or 0)
    peak_prominence = max(float(peak_prominence or 0), 0.0)
    peak_window = max(int(peak_window or 1), 1)

    kept_indices = {0, n - 1}
    reasons = {
        0: {"endpoint"},
        n - 1: {"endpoint"},
    }
    slope_count = 0
    peak_count = 0
    valley_count = 0
    spacing_count = 0

    def add_keep(idx, reason):
        kept_indices.add(idx)
        reasons.setdefault(idx, set()).add(reason)

    def same_height(a, b):
        return abs(a - b) <= 1e-9

    # 1) Shape-critical points: slope changes and local peaks/valleys.
    for i in range(1, n - 1):
        dx_in = x[i] - x[i - 1]
        dx_out = x[i + 1] - x[i]

        if dx_in == 0 or dx_out == 0:
            slope_change = float("inf")
        else:
            slope_in = (y[i] - y[i - 1]) / dx_in
            slope_out = (y[i + 1] - y[i]) / dx_out
            slope_change = abs(slope_in - slope_out)

        if slope_change > slope_threshold:
            add_keep(i, "slope")
            slope_count += 1

        # Do not keep every point in a flat top/bottom plateau.  The first point
        # of the plateau is enough; subsequent equal-height points are skipped
        # unless they were already kept as slope-change points.
        if same_height(y[i], y[i - 1]):
            continue

        lo = max(0, i - peak_window)
        hi = min(n, i + peak_window + 1)
        left_values = y[lo:i]
        right_values = y[i + 1 : hi]
        if not left_values or not right_values:
            continue

        left_min = min(left_values)
        right_min = min(right_values)
        left_max = max(left_values)
        right_max = max(right_values)

        peak_strength = min(y[i] - left_min, y[i] - right_min)
        valley_strength = min(left_max - y[i], right_max - y[i])

        is_peak = (
            y[i] >= left_max
            and y[i] >= right_max
            and peak_strength >= peak_prominence
        )
        is_valley = (
            y[i] <= left_min
            and y[i] <= right_min
            and valley_strength >= peak_prominence
        )

        if is_peak:
            add_keep(i, "peak")
            peak_count += 1
        elif is_valley:
            add_keep(i, "valley")
            valley_count += 1

    # 2) Low-priority spacing points.  These are added only after all critical
    # points are fixed, so they never replace slope/peak/valley points.
    if max_dist > 0:
        while True:
            ordered = sorted(kept_indices)
            added = False

            for left_idx, right_idx in zip(ordered, ordered[1:]):
                gap = x[right_idx] - x[left_idx]
                if gap <= max_dist:
                    continue

                inner = [
                    idx
                    for idx in range(left_idx + 1, right_idx)
                    if idx not in kept_indices
                ]
                if not inner:
                    continue

                target_x = x[left_idx] + max_dist
                best_idx = min(inner, key=lambda idx: abs(x[idx] - target_x))
                add_keep(best_idx, "spacing")
                spacing_count += 1
                added = True
                break

            if not added:
                break

    kept_indices = sorted(kept_indices)

    log_func(
        f" ✂️ 데이터 압축: {len(df)}개 -> {len(kept_indices)}개 "
        f"(기울기 {slope_count}개, 고점 {peak_count}개, 저점 {valley_count}개, "
        f"보조거리 {spacing_count}개, peak_prominence {peak_prominence}m)"
    )

    return df.iloc[kept_indices].drop(
        columns=["누가거리_num", "관저고_num"], errors="ignore"
    ).copy()


def add_result_column(df):
    result_df = df.copy()
    result_df["결과"] = (
        "관저고 "
        + result_df["관저고"].astype(str)
        + " 에 누가거리 "
        + result_df["누가거리"].astype(str)
    )
    return result_df


def save_compat_24_excel(filtered_df, output_path):
    """Save exactly in the 2.4 output shape."""
    result_df = add_result_column(filtered_df)
    safe_path = safe_output_path(output_path)
    result_df[["관저고", "누가거리", "결과"]].to_excel(
        safe_path, index=False, engine="openpyxl"
    )
    return safe_path

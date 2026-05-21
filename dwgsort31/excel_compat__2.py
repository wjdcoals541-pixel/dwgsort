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
    height_error_threshold=0.50,
    peak_window=2,
):
    """
    2.4-compatible point compression, revised priority model.

    Priority:
    1) Start/end points are always kept.
    2) Slope-change points are always kept.
    3) Real local high/low points compared with surrounding nodes are kept.
    4) Points that would hide an important vertical deviation are kept.
    5) max_dist is used only as a low-priority filler for visually empty gaps.

    Notes:
    - The old max_dist behavior was a hard "distance keep" rule inside the main loop.
      Here it is applied only after important shape points are selected.
    - peak_prominence and height_error_threshold are intentionally more conservative
      than the previous patch to avoid keeping many near-duplicate plateau points.
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
        .drop_duplicates(subset=["누가거리_num"])
        .reset_index(drop=True)
    )

    if len(df) <= 2:
        return df.drop(columns=["누가거리_num", "관저고_num"], errors="ignore").copy()

    n = len(df)
    x = df["누가거리_num"].to_numpy(dtype=float)
    y = df["관저고_num"].to_numpy(dtype=float)

    slope_threshold = max(float(slope_threshold), 0.0)
    max_dist = max(float(max_dist), 0.0)
    peak_prominence = max(float(peak_prominence), 0.0)
    height_error_threshold = max(float(height_error_threshold), 0.0)
    peak_window = max(int(peak_window), 1)

    kept = {0, n - 1}
    reasons = {0: {"endpoint"}, n - 1: {"endpoint"}}
    slope_changes = [0.0] * n
    local_scores = [0.0] * n

    def mark(idx, reason):
        kept.add(idx)
        reasons.setdefault(idx, set()).add(reason)

    def safe_slope(left_idx, right_idx):
        dx = x[right_idx] - x[left_idx]
        if dx == 0:
            return None
        return (y[right_idx] - y[left_idx]) / dx

    def interpolated_y(left_idx, right_idx, target_x):
        dx = x[right_idx] - x[left_idx]
        if dx == 0:
            return y[left_idx]
        ratio = (target_x - x[left_idx]) / dx
        return y[left_idx] + ratio * (y[right_idx] - y[left_idx])

    # 1) Shape-critical points: slope changes and strict local peaks/valleys.
    for i in range(1, n - 1):
        slope_in = safe_slope(i - 1, i)
        slope_out = safe_slope(i, i + 1)

        if slope_in is None or slope_out is None:
            slope_change = float("inf")
        else:
            slope_change = abs(slope_out - slope_in)

        slope_changes[i] = slope_change
        if slope_change > slope_threshold:
            mark(i, "slope")

        lo = max(0, i - peak_window)
        hi = min(n, i + peak_window + 1)
        neighbor_values = [y[j] for j in range(lo, hi) if j != i]
        if not neighbor_values:
            continue

        neighbor_max = max(neighbor_values)
        neighbor_min = min(neighbor_values)

        # Strict comparison prevents whole flat plateaus from being kept.
        peak_prom = y[i] - neighbor_max
        valley_prom = neighbor_min - y[i]

        is_local_peak = peak_prom >= peak_prominence
        is_local_valley = valley_prom >= peak_prominence

        if is_local_peak:
            mark(i, "peak")
        if is_local_valley:
            mark(i, "valley")

        local_scores[i] = max(peak_prom, valley_prom, 0.0)

    # 2) Add only points that would visibly distort the height shape if skipped.
    #    This is intentionally conservative; small 0.1m wiggles should not explode the result count.
    while True:
        ordered = sorted(kept, key=lambda idx: x[idx])
        worst_idx = None
        worst_error = 0.0

        for left, right in zip(ordered, ordered[1:]):
            if right <= left + 1:
                continue

            for i in range(left + 1, right):
                line_y = interpolated_y(left, right, x[i])
                error = abs(y[i] - line_y)
                if error > worst_error:
                    worst_error = error
                    worst_idx = i

        if worst_idx is None or worst_error < height_error_threshold:
            break

        mark(worst_idx, "height_error")

    # 3) Low-priority distance fillers. They are added only after shape points are fixed.
    filler_count = 0
    if max_dist > 0:
        while True:
            ordered = sorted(kept, key=lambda idx: x[idx])
            added = False

            for left, right in zip(ordered, ordered[1:]):
                gap = x[right] - x[left]
                if gap <= max_dist:
                    continue

                inner = [i for i in range(left + 1, right) if i not in kept]
                if not inner:
                    continue

                target_x = x[left] + max_dist

                def filler_rank(idx):
                    # Distance filler is mainly for visual spacing.
                    # If candidates are similarly placed, prefer the one with more shape meaning.
                    distance_score = abs(x[idx] - target_x)
                    shape_score = local_scores[idx] + slope_changes[idx]
                    return (distance_score, -shape_score)

                best = min(inner, key=filler_rank)
                mark(best, "distance_filler")
                filler_count += 1
                added = True
                break

            if not added:
                break

    kept_indices = sorted(kept, key=lambda idx: x[idx])

    reason_count = {}
    for idx in kept_indices:
        for reason in reasons.get(idx, []):
            reason_count[reason] = reason_count.get(reason, 0) + 1

    log_func(
        " ✂️ 데이터 압축: "
        f"{len(df)}개 -> {len(kept_indices)}개 "
        f"(기울기 {reason_count.get('slope', 0)}개, "
        f"고점 {reason_count.get('peak', 0)}개, "
        f"저점 {reason_count.get('valley', 0)}개, "
        f"높이오차 {reason_count.get('height_error', 0)}개, "
        f"거리보조 {filler_count}개)"
    )

    return df.iloc[kept_indices].drop(
        columns=["누가거리_num", "관저고_num"],
        errors="ignore",
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

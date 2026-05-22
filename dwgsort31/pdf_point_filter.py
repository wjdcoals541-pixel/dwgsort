import pandas as pd


def filter_pdf_graph_points(
    df: pd.DataFrame,
    log_func,
    slope_threshold: float,
    max_dist: float,
    peak_prominence: float,
) -> pd.DataFrame:
    """PDF-specific point filtering logic.

    Enforces a minimum spacing of 1.0m between final points.
    Does not use Y tolerance.
    Processes each line_id independently if present.
    """
    df = df.copy()

    # Convert coordinates to numeric for filtering
    df["누가거리_num"] = pd.to_numeric(
        df["누가거리"].astype(str).str.replace(",", "", regex=False),
        errors="coerce",
    )
    df["관저고_num"] = pd.to_numeric(
        df["관저고"].astype(str).str.replace(",", "", regex=False),
        errors="coerce",
    )

    # Filter out invalid entries and sort
    df_clean = df.dropna(subset=["누가거리_num", "관저고_num"])
    if df_clean.empty:
        log_func("[PDF] 점 정리 적용: 원본 0개 -> 정리 0개")
        log_func(f"[PDF] 적용 설정: 기울기={slope_threshold}, 거리={max_dist}, 고점={peak_prominence}, 최소간격=1.0m")
        log_func("[PDF] Y오차는 PDF 점 정리에 사용하지 않음")
        return df_clean.drop(columns=["누가거리_num", "관저고_num"], errors="ignore")

    total_raw = len(df_clean)

    slope_threshold = float(slope_threshold or 0)
    max_dist = max(float(max_dist or 0), 0.0)
    peak_prominence = max(float(peak_prominence or 0), 0.0)
    min_spacing = 1.0

    # Group by line_id or 라인명 if present, otherwise process as a single group
    group_col = None
    if "line_id" in df_clean.columns:
        group_col = "line_id"
    elif "라인명" in df_clean.columns:
        group_col = "라인명"

    result_indices = []

    if group_col:
        # Sort by group_col and then by 누가거리_num
        df_clean = df_clean.sort_values(by=[group_col, "누가거리_num"])
        groups = df_clean.groupby(group_col, sort=False)
    else:
        df_clean = df_clean.sort_values(by="누가거리_num")
        groups = [("all", df_clean)]

    for group_name, sub_df in groups:
        sub_df = sub_df.drop_duplicates(subset=["누가거리_num"], keep="first")
        n = len(sub_df)
        if n == 0:
            continue
        if n <= 2:
            result_indices.extend(sub_df.index.tolist())
            continue

        x = sub_df["누가거리_num"].tolist()
        y = sub_df["관저고_num"].tolist()
        indices = sub_df.index.tolist()

        kept_indices_in_sub = {0, n - 1}
        peaks = []
        valleys = []
        peak_window = 2

        def same_height(a, b):
            return abs(a - b) <= 1e-9

        # 1) Detect peaks and valleys
        for i in range(1, n - 1):
            if same_height(y[i], y[i - 1]):
                continue

            lo = max(0, i - peak_window)
            hi = min(n, i + peak_window + 1)
            left_values = y[lo:i]
            right_values = y[i + 1: hi]
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
                peaks.append((i, peak_strength))
            elif is_valley:
                valleys.append((i, valley_strength))

        # Sort peaks and valleys by strength descending
        peaks_and_valleys = sorted(peaks + valleys, key=lambda item: item[1], reverse=True)

        # 2) Keep peaks/valleys if they satisfy min_spacing
        for idx, strength in peaks_and_valleys:
            too_close = False
            for k in kept_indices_in_sub:
                if abs(x[idx] - x[k]) < min_spacing:
                    too_close = True
                    break
            if not too_close:
                kept_indices_in_sub.add(idx)

        # 3) Detect slope change points
        slope_changes = []
        for i in range(1, n - 1):
            if i in kept_indices_in_sub:
                continue

            dx_in = x[i] - x[i - 1]
            dx_out = x[i + 1] - x[i]
            if dx_in == 0 or dx_out == 0:
                slope_change = float("inf")
            else:
                slope_in = (y[i] - y[i - 1]) / dx_in
                slope_out = (y[i + 1] - y[i]) / dx_out
                slope_change = abs(slope_in - slope_out)

            if slope_change > slope_threshold:
                slope_changes.append((i, slope_change))

        # Sort slope changes by magnitude descending
        slope_changes.sort(key=lambda item: item[1], reverse=True)

        for idx, change in slope_changes:
            too_close = False
            for k in kept_indices_in_sub:
                if abs(x[idx] - x[k]) < min_spacing:
                    too_close = True
                    break
            if not too_close:
                kept_indices_in_sub.add(idx)

        # 4) Add low-priority spacing points (max_dist)
        if max_dist > 0:
            while True:
                ordered = sorted(kept_indices_in_sub)
                added = False
                for left_idx, right_idx in zip(ordered, ordered[1:]):
                    gap = x[right_idx] - x[left_idx]
                    if gap <= max_dist:
                        continue
                    inner = [
                        idx
                        for idx in range(left_idx + 1, right_idx)
                        if idx not in kept_indices_in_sub
                    ]
                    if not inner:
                        continue

                    target_x = x[left_idx] + max_dist
                    valid_inner = []
                    for idx in inner:
                        too_close = False
                        for k in kept_indices_in_sub:
                            if abs(x[idx] - x[k]) < min_spacing:
                                too_close = True
                                break
                        if not too_close:
                            valid_inner.append(idx)

                    if not valid_inner:
                        continue

                    best_idx = min(valid_inner, key=lambda idx: abs(x[idx] - target_x))
                    kept_indices_in_sub.add(best_idx)
                    added = True
                    break
                if not added:
                    break

        # Map sub_df local indices back to global DataFrame index
        for idx in sorted(kept_indices_in_sub):
            result_indices.append(indices[idx])

    filtered_df = df.loc[result_indices].copy()
    total_filtered = len(filtered_df)

    log_func(f"[PDF] 점 정리 적용: 원본 {total_raw}개 -> 정리 {total_filtered}개")
    log_func(f"[PDF] 적용 설정: 기울기={slope_threshold}, 거리={max_dist}, 고점={peak_prominence}, 최소간격=1.0m")
    log_func("[PDF] Y오차는 PDF 점 정리에 사용하지 않음")

    # Clean up temporary helper columns
    filtered_df = filtered_df.drop(columns=["누가거리_num", "관저고_num"], errors="ignore")
    if "증가거리" in filtered_df.columns:
        filtered_df = _recalculate_increase_distance(filtered_df)
    return filtered_df


def _recalculate_increase_distance(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    group_col = "line_id" if "line_id" in df.columns else None
    groups = df.groupby(group_col, sort=False) if group_col else [("all", df)]
    df["증가거리"] = "-"

    for _, sub_df in groups:
        previous = None
        for index, value in sub_df["누가거리"].items():
            current = pd.to_numeric(str(value).replace(",", ""), errors="coerce")
            if pd.isna(current):
                previous = None
                continue
            if previous is not None:
                df.at[index, "증가거리"] = f"{current - previous:.2f}"
            previous = current

    return df

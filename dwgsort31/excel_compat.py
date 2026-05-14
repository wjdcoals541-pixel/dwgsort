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


def filter_graph_points_24(df, log_func, slope_threshold, max_dist):
    """2.4-compatible point compression."""
    df = df.copy()
    df["누가거리_num"] = pd.to_numeric(
        df["누가거리"].astype(str).str.replace(",", "", regex=False), errors="coerce"
    )
    df["관저고_num"] = pd.to_numeric(
        df["관저고"].astype(str).str.replace(",", "", regex=False), errors="coerce"
    )
    df = df.dropna(subset=["누가거리_num", "관저고_num"]).reset_index(drop=True)

    if len(df) <= 2:
        return df.drop(columns=["누가거리_num", "관저고_num"], errors="ignore").copy()

    kept_indices = [0]
    last_kept_idx = 0

    for i in range(1, len(df) - 1):
        x_prev = df.loc[last_kept_idx, "누가거리_num"]
        y_prev = df.loc[last_kept_idx, "관저고_num"]
        x_curr = df.loc[i, "누가거리_num"]
        y_curr = df.loc[i, "관저고_num"]
        x_next = df.loc[i + 1, "누가거리_num"]
        y_next = df.loc[i + 1, "관저고_num"]

        dx_in = x_curr - x_prev
        dy_in = y_curr - y_prev
        dx_out = x_next - x_curr
        dy_out = y_next - y_curr

        if dx_in > max_dist:
            kept_indices.append(i)
            last_kept_idx = i
            continue

        if dx_in == 0 or dx_out == 0:
            kept_indices.append(i)
            last_kept_idx = i
            continue

        slope_change = abs((dy_in / dx_in) - (dy_out / dx_out))
        if slope_change > slope_threshold:
            kept_indices.append(i)
            last_kept_idx = i

    if kept_indices[-1] != len(df) - 1:
        kept_indices.append(len(df) - 1)

    log_func(f" ✂️ 데이터 압축(변곡점): {len(df)}개 -> {len(kept_indices)}개")
    return df.iloc[kept_indices].drop(columns=["누가거리_num", "관저고_num"]).copy()


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

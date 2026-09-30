import os


def filter_profile_groups(df, filter_func, *args, **kwargs):
    import pandas as pd

    groups = []
    for line_id, group in df.groupby("line_id", sort=False):
        filtered = filter_func(group.drop(columns="line_id"), *args, **kwargs)
        filtered["line_id"] = line_id
        groups.append(filtered)
    return pd.concat(groups, ignore_index=True)[df.columns]


def result_columns(df):
    return (["line_id"] if "line_id" in df else []) + ["관저고", "누가거리", "결과"]


def safe_output_path(output_path):
    """Return an unused path by appending _vN when a file already exists."""
    if not os.path.exists(output_path):
        return output_path

    base, ext = os.path.splitext(output_path)
    counter = 2
    while True:
        candidate = f"{base}_v{counter}{ext}"
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def is_supported_file(path, extensions):
    return os.path.isfile(path) and path.lower().endswith(extensions)

import platform


def preview_profile(df, title):
    import matplotlib.pyplot as plt
    import pandas as pd

    if platform.system() == "Windows":
        plt.rc("font", family="Malgun Gothic")
    plt.rc("axes", unicode_minus=False)

    plot_df = pd.DataFrame(
        {
            "x": pd.to_numeric(df["누가거리"].astype(str).str.replace(",", "", regex=False), errors="coerce"),
            "y": pd.to_numeric(df["관저고"].astype(str).str.replace(",", "", regex=False), errors="coerce"),
            "line_id": df["line_id"] if "line_id" in df.columns else 1,
        }
    ).dropna(subset=["x", "y"])

    plt.figure(figsize=(10, 5))
    for _line_id, group in plot_df.groupby("line_id", sort=False):
        plt.plot(group["x"], group["y"], marker="o", linestyle="-", color="blue", markersize=5)
    plt.title(title)
    plt.xlabel("누가거리 (m)")
    plt.ylabel("관저고 (m)")
    plt.grid(True, linestyle="--", alpha=0.7)
    plt.tight_layout()
    plt.show()

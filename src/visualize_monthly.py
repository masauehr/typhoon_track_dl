"""Phase1: 月別台風トラックの可視化（古典的検証）。

MANUAL.mdの進め方に基づき、月別に全トラックを東アジア地図に重ね書きし、
既知の季節傾向（夏は日本近海で北上、秋は南下してから再カーブする経路が
増える等）と整合するかを目視で確認する。ここで明らかな傾向が見えない
場合は、データ処理か仮説自体を見直す。
"""
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import pandas as pd

plt.rcParams["font.family"] = "Hiragino Sans"

DATA_PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"

MAP_EXTENT = [100, 180, 0, 50]  # 東アジア〜西太平洋


def load_tracks_with_origin_month() -> pd.DataFrame:
    """観測点CSVを読み込み、台風ごとの発生月（最初の観測点の月）を付与する。"""
    df = pd.read_csv(DATA_PROCESSED_DIR / "best_track.csv", parse_dates=["datetime"])
    origin_month = (
        df.sort_values("datetime")
        .groupby("international_id")["datetime"]
        .first()
        .dt.month
        .rename("origin_month")
    )
    return df.merge(origin_month, on="international_id")


def plot_monthly_tracks(df: pd.DataFrame, out_path: Path) -> None:
    """1〜12月それぞれの台風進路を東アジア地図に重ね書きしたパネル図を保存する。"""
    fig, axes = plt.subplots(
        3, 4, figsize=(20, 14), subplot_kw={"projection": ccrs.PlateCarree()}
    )

    for month, ax in zip(range(1, 13), axes.flat):
        ax.set_extent(MAP_EXTENT, crs=ccrs.PlateCarree())
        ax.add_feature(cfeature.LAND, facecolor="0.9")
        ax.add_feature(cfeature.COASTLINE, linewidth=0.5)

        month_df = df[df["origin_month"] == month]
        n_typhoons = month_df["international_id"].nunique()
        for _, track in month_df.groupby("international_id"):
            track = track.sort_values("datetime")
            ax.plot(
                track["lon"],
                track["lat"],
                transform=ccrs.PlateCarree(),
                color="tab:red",
                alpha=0.15,
                linewidth=0.8,
            )
        ax.set_title(f"{month}月 (n={n_typhoons})", fontsize=11)

    fig.suptitle(
        "月別 台風進路（発生月ベース、1951-2026年 気象庁ベストトラック）", fontsize=16
    )
    fig.tight_layout()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"出力: {out_path}")


if __name__ == "__main__":
    df = load_tracks_with_origin_month()
    plot_monthly_tracks(df, OUTPUT_DIR / "phase1_monthly_tracks.png")

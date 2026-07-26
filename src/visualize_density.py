"""Phase1補足: 月別・台風通過密度ヒートマップ。

visualize_monthly.py の重ね書き図（線が多いほど濃く見えるが定量的ではない）に対し、
台風がどこを最も多く通ったかをグリッド集計で定量的に示す。各トラックを線分に沿って
密に補間してから2次元ヒストグラムを取り、ガウシアン平滑化して滑らかな密度分布にする。

配色は dataviz skill の sequential blue ランプ（references/palette.md）を使用。
"""
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from scipy.ndimage import gaussian_filter

plt.rcParams["font.family"] = "Hiragino Sans"

DATA_PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"

MAP_EXTENT = [100, 180, 0, 50]  # 東アジア〜西太平洋
GRID_STEP = 0.5  # 度単位のグリッド解像度
INTERP_STEP_DEG = 0.3  # トラック補間の点間隔（度、概ね30km）
SMOOTH_SIGMA = 1.2  # ガウシアン平滑化のグリッドセル数

# dataviz skill: sequential blue（references/palette.md, step 100〜700）
SEQUENTIAL_BLUE = [
    "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
    "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b",
]


def load_tracks_with_origin_month() -> pd.DataFrame:
    df = pd.read_csv(DATA_PROCESSED_DIR / "best_track.csv", parse_dates=["datetime"])
    origin_month = (
        df.sort_values("datetime")
        .groupby("international_id")["datetime"]
        .first()
        .dt.month
        .rename("origin_month")
    )
    return df.merge(origin_month, on="international_id")


def densify_track(lat: np.ndarray, lon: np.ndarray, step_deg: float = INTERP_STEP_DEG) -> tuple:
    """観測点(6時間毎)間を線分沿いに一定間隔で補間し、密な点列にする。"""
    dense_lats, dense_lons = [], []
    for i in range(len(lat) - 1):
        seg_len = np.hypot(lat[i + 1] - lat[i], lon[i + 1] - lon[i])
        n_points = max(int(seg_len / step_deg), 1)
        t = np.linspace(0, 1, n_points, endpoint=False)
        dense_lats.append(lat[i] + t * (lat[i + 1] - lat[i]))
        dense_lons.append(lon[i] + t * (lon[i + 1] - lon[i]))
    dense_lats.append(lat[-1:])
    dense_lons.append(lon[-1:])
    return np.concatenate(dense_lats), np.concatenate(dense_lons)


def compute_density_grid(month_df: pd.DataFrame) -> tuple:
    """月別データから密な点群を作り、2次元ヒストグラム→平滑化した密度グリッドを返す。"""
    lon_edges = np.arange(MAP_EXTENT[0], MAP_EXTENT[1] + GRID_STEP, GRID_STEP)
    lat_edges = np.arange(MAP_EXTENT[2], MAP_EXTENT[3] + GRID_STEP, GRID_STEP)

    all_lats, all_lons = [], []
    for _, track in month_df.groupby("international_id"):
        track = track.sort_values("datetime")
        if len(track) < 2:
            continue
        dlat, dlon = densify_track(track["lat"].to_numpy(), track["lon"].to_numpy())
        all_lats.append(dlat)
        all_lons.append(dlon)

    lats = np.concatenate(all_lats)
    lons = np.concatenate(all_lons)
    density, _, _ = np.histogram2d(lats, lons, bins=[lat_edges, lon_edges])
    density = gaussian_filter(density, sigma=SMOOTH_SIGMA)
    return density, lon_edges, lat_edges


def plot_monthly_density(df: pd.DataFrame, out_path: Path) -> None:
    """月別に台風の通過密度ヒートマップを12パネルで描画する。"""
    cmap = LinearSegmentedColormap.from_list("sequential_blue", SEQUENTIAL_BLUE)

    fig, axes = plt.subplots(
        3, 4, figsize=(20, 14), subplot_kw={"projection": ccrs.PlateCarree()}
    )

    # 月ごとに密度を最大値1へ正規化する。台風数が少ない月（1-2月等）でも
    # 「その月で最も多く通った経路」が見えるようにするための選択（絶対数の
    # 月比較をしたい場合は正規化前のdensity.max()を別途参照）。
    for month, ax in zip(range(1, 13), axes.flat):
        ax.set_extent(MAP_EXTENT, crs=ccrs.PlateCarree())
        ax.add_feature(cfeature.LAND, facecolor="0.9", zorder=0)
        ax.add_feature(cfeature.COASTLINE, linewidth=0.5, zorder=2)

        month_df = df[df["origin_month"] == month]
        density, lon_edges, lat_edges = compute_density_grid(month_df)
        n_typhoons = month_df["international_id"].nunique()
        normalized = density / density.max()
        masked = np.ma.masked_where(normalized <= 0.02, normalized)
        mesh = ax.pcolormesh(
            lon_edges, lat_edges, masked,
            cmap=cmap, vmin=0, vmax=1,
            transform=ccrs.PlateCarree(), zorder=1,
        )
        ax.set_title(f"{month}月 (n={n_typhoons})", fontsize=11)

    fig.suptitle(
        "月別 台風通過密度（発生月ベース、1951-2026年 気象庁ベストトラック）\n"
        "色が濃いほど、その月の中で最も多く通った経路（月ごとに最大値1へ正規化）", fontsize=15
    )
    fig.subplots_adjust(right=0.90)
    cbar_ax = fig.add_axes([0.92, 0.15, 0.015, 0.7])
    fig.colorbar(mesh, cax=cbar_ax, label="通過密度（月内最大値=1に正規化）")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"出力: {out_path}")


if __name__ == "__main__":
    df = load_tracks_with_origin_month()
    plot_monthly_density(df, OUTPUT_DIR / "phase1_monthly_density.png")

"""Phase1追加分析: 10年ごとの台風進路の変化を調べる。

年代（発生年の10年区切り）ごとに、
1) 通過密度ヒートマップ（visualize_density.pyと同じ手法）
2) 発生位置・到達緯度・強度の統計トレンド
3) SOMノード（Phase2）出現比率の年代推移
を可視化し、経路パターンに経年変化があるかを確認する。

注意: 2020年代は2020-2026年の7年分（他は10年分）とサンプル期間が短い。
また1950-60年代は衛星観測以前で弱い熱帯低気圧の捕捉率が低い可能性があり、
最大風速は1977年以降のみ記録されている点に留意して解釈すること。
"""
from pathlib import Path

import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from scipy.ndimage import gaussian_filter

from visualize_density import MAP_EXTENT, SEQUENTIAL_BLUE, compute_density_grid

plt.rcParams["font.family"] = "Hiragino Sans"

DATA_PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"

# dataviz skill: categorical slot 1 (blue) / slot 2 (orange) — references/palette.md
COLOR_BLUE = "#2a78d6"
COLOR_ORANGE = "#eb6834"


def load_tracks_with_decade() -> pd.DataFrame:
    df = pd.read_csv(DATA_PROCESSED_DIR / "best_track.csv", parse_dates=["datetime"])
    origin_year = (
        df.sort_values("datetime")
        .groupby("international_id")["datetime"]
        .first()
        .dt.year
        .rename("origin_year")
    )
    df = df.merge(origin_year, on="international_id")
    df["decade"] = (df["origin_year"] // 10) * 10
    return df


def decade_label(decade: int, df: pd.DataFrame) -> str:
    """年代ラベルを作る。データ末尾の年代は実際の年範囲（不完全な10年）を明記する。"""
    max_year = df["origin_year"].max()
    end = min(decade + 9, max_year)
    n = df.loc[df["decade"] == decade, "international_id"].nunique()
    return f"{decade}-{end}年 (n={n})"


def plot_decadal_density(df: pd.DataFrame, out_path: Path) -> None:
    """年代別の台風通過密度ヒートマップ（月内正規化と同じ考え方で年代内正規化）。"""
    cmap = LinearSegmentedColormap.from_list("sequential_blue", SEQUENTIAL_BLUE)
    decades = sorted(df["decade"].unique())

    fig, axes = plt.subplots(
        2, 4, figsize=(20, 10), subplot_kw={"projection": ccrs.PlateCarree()}
    )

    mesh = None
    for decade, ax in zip(decades, axes.flat):
        ax.set_extent(MAP_EXTENT, crs=ccrs.PlateCarree())
        ax.add_feature(cfeature.LAND, facecolor="0.9", zorder=0)
        ax.add_feature(cfeature.COASTLINE, linewidth=0.5, zorder=2)

        decade_df = df[df["decade"] == decade]
        density, lon_edges, lat_edges = compute_density_grid(decade_df)
        normalized = density / density.max()
        masked = np.ma.masked_where(normalized <= 0.02, normalized)
        mesh = ax.pcolormesh(
            lon_edges, lat_edges, masked,
            cmap=cmap, vmin=0, vmax=1,
            transform=ccrs.PlateCarree(), zorder=1,
        )
        ax.set_title(decade_label(decade, df), fontsize=11)

    # 未使用パネルを消す（8年代ちょうどなら不要）
    for ax in axes.flat[len(decades):]:
        ax.axis("off")

    fig.suptitle(
        "年代別 台風通過密度（発生年ベース、気象庁ベストトラック）\n"
        "色が濃いほど、その年代の中で最も多く通った経路（年代ごとに最大値1へ正規化）",
        fontsize=15,
    )
    fig.subplots_adjust(right=0.90)
    cbar_ax = fig.add_axes([0.92, 0.15, 0.015, 0.7])
    fig.colorbar(mesh, cax=cbar_ax, label="通過密度（年代内最大値=1に正規化）")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"出力: {out_path}")


def compute_decadal_stats(df: pd.DataFrame) -> pd.DataFrame:
    """台風ごとに発生位置・到達緯度・最盛期強度を求め、年代別に平均する。"""
    per_typhoon = df.groupby("international_id").agg(
        decade=("decade", "first"),
        origin_lat=("lat", "first"),
        origin_lon=("lon", "first"),
        max_lat=("lat", "max"),
        min_pressure=("pressure", "min"),
        max_wind=("max_wind", "max"),
    )
    return per_typhoon.groupby("decade").agg(
        n=("origin_lat", "size"),
        origin_lat_mean=("origin_lat", "mean"),
        origin_lon_mean=("origin_lon", "mean"),
        max_lat_mean=("max_lat", "mean"),
        min_pressure_mean=("min_pressure", "mean"),
        max_wind_mean=("max_wind", "mean"),
    )


def plot_decadal_stats(stats: pd.DataFrame, out_path: Path) -> None:
    """発生緯度・到達緯度・最低気圧・最大風速の年代トレンドを折れ線で並べる。"""
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    x = stats.index.astype(str) + "s"

    ax = axes[0, 0]
    ax.plot(x, stats["origin_lat_mean"], "o-", color=COLOR_BLUE)
    ax.set_title("平均発生緯度（北上するほど値が大きい）")
    ax.set_ylabel("緯度 (°N)")

    ax = axes[0, 1]
    ax.plot(x, stats["max_lat_mean"], "o-", color=COLOR_BLUE)
    ax.set_title("平均到達最大緯度（進路がどこまで北上したか）")
    ax.set_ylabel("緯度 (°N)")

    ax = axes[1, 0]
    ax.plot(x, stats["min_pressure_mean"], "o-", color=COLOR_ORANGE)
    ax.set_title("平均最低中心気圧（低いほど強い台風）")
    ax.set_ylabel("hPa")
    ax.invert_yaxis()

    ax = axes[1, 1]
    ax.plot(x, stats["max_wind_mean"], "o-", color=COLOR_ORANGE)
    ax.set_title("平均最大風速（1977年以降のみ記録）")
    ax.set_ylabel("kt")

    for ax in axes.flat:
        ax.tick_params(axis="x", rotation=45)
        ax.grid(True, alpha=0.3)

    fig.suptitle("年代別 台風の発生位置・強度トレンド（発生年ベース）", fontsize=15)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"出力: {out_path}")


def plot_decadal_som_composition(out_path: Path, df: pd.DataFrame) -> None:
    """Phase2で求めたSOMノード割当に発生年を結合し、年代別出現比率を積み上げ棒で示す。"""
    assignment_path = DATA_PROCESSED_DIR / "som_assignment.csv"
    if not assignment_path.exists():
        print(f"スキップ: {assignment_path} が無いため src/som_cluster.py を先に実行してください。")
        return

    assignment = pd.read_csv(assignment_path)
    origin_year = (
        df.sort_values("datetime")
        .groupby("international_id")["datetime"]
        .first()
        .dt.year
        .rename("origin_year")
    )
    assignment = assignment.merge(origin_year, on="international_id")
    assignment["decade"] = (assignment["origin_year"] // 10) * 10

    # som_cluster.py の node_color と同じ規則で色を割り当てる（5x5グリッド前提）
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from som_cluster import SOM_SHAPE, node_color

    n_rows, n_cols = SOM_SHAPE
    node_order = [f"{r}-{c}" for r in range(n_rows) for c in range(n_cols)]
    colors = [node_color(r, c, n_rows, n_cols) for r in range(n_rows) for c in range(n_cols)]

    counts = assignment.groupby(["decade", "node"]).size().unstack(fill_value=0)
    counts = counts.reindex(columns=node_order, fill_value=0)
    ratios = counts.div(counts.sum(axis=1), axis=0)

    fig, ax = plt.subplots(figsize=(12, 7))
    ratios.index = [decade_label(d, df) for d in ratios.index]
    ratios.plot(kind="bar", stacked=True, ax=ax, color=colors, width=0.8)
    ax.set_xlabel("年代")
    ax.set_ylabel("SOMノード別出現比率")
    ax.set_title("年代別 SOMノード出現比率（進路パターンの経年変化）")
    ax.legend(title="node", bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8, ncol=2)
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"出力: {out_path}")


if __name__ == "__main__":
    df = load_tracks_with_decade()

    plot_decadal_density(df, OUTPUT_DIR / "decadal_density.png")

    stats = compute_decadal_stats(df)
    print(stats.round(2))
    stats.to_csv(DATA_PROCESSED_DIR / "decadal_stats.csv")
    plot_decadal_stats(stats, OUTPUT_DIR / "decadal_stats.png")

    plot_decadal_som_composition(OUTPUT_DIR / "decadal_som_composition.png", df)

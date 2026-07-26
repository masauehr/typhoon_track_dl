"""Phase2: SOM（自己組織化マップ）による台風進路パターンのクラスタリング。

MANUAL.mdの方針に基づき、台風ごとの緯度経度時系列を固定長にリサンプリングして
特徴ベクトル化し、MiniSomで教師なしクラスタリングする。各SOMノードを
代表的な進路パターン（直進型・再カーブ型等）として解釈し、月別の出現比率を集計する。
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from minisom import MiniSom

plt.rcParams["font.family"] = "Hiragino Sans"

DATA_PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "outputs"

MAP_EXTENT = [100, 180, 0, 50]  # 東アジア〜西太平洋
N_RESAMPLE = 20  # トラック1本あたりのリサンプリング点数
MIN_POINTS = 4  # これ未満の観測点数の台風は除外（線形補間の安定性のため）
SOM_SHAPE = (5, 5)  # SOMグリッドの形状（縦, 横）
RANDOM_SEED = 0


def resample_track(lat: np.ndarray, lon: np.ndarray, n: int = N_RESAMPLE) -> np.ndarray:
    """緯度経度の時系列を、時系列上の進行度（0〜1）に沿って等間隔にn点へ線形補間する。

    Returns:
        shape (2n,) の1次元配列 [lat_0..lat_{n-1}, lon_0..lon_{n-1}]
    """
    original_progress = np.linspace(0, 1, len(lat))
    target_progress = np.linspace(0, 1, n)
    lat_resampled = np.interp(target_progress, original_progress, lat)
    lon_resampled = np.interp(target_progress, original_progress, lon)
    return np.concatenate([lat_resampled, lon_resampled])


def build_feature_matrix(df: pd.DataFrame) -> tuple[np.ndarray, pd.DataFrame]:
    """観測点DataFrameから、台風ごとの特徴ベクトル行列と台風メタ情報を作る。"""
    features = []
    meta_records = []

    for international_id, track in df.groupby("international_id"):
        track = track.sort_values("datetime")
        if len(track) < MIN_POINTS:
            continue
        features.append(resample_track(track["lat"].to_numpy(), track["lon"].to_numpy()))
        meta_records.append(
            {
                "international_id": international_id,
                "name": track["name"].iloc[0],
                "origin_month": track["datetime"].iloc[0].month,
                "n_points": len(track),
            }
        )

    return np.array(features), pd.DataFrame.from_records(meta_records)


def train_som(features: np.ndarray) -> MiniSom:
    """特徴量を正規化してMiniSomを学習する。"""
    som = MiniSom(
        SOM_SHAPE[0],
        SOM_SHAPE[1],
        features.shape[1],
        sigma=1.0,
        learning_rate=0.5,
        neighborhood_function="gaussian",
        random_seed=RANDOM_SEED,
    )
    som.pca_weights_init(features)
    som.train(features, 5000, verbose=False)
    return som


def assign_nodes(som: MiniSom, features: np.ndarray, meta: pd.DataFrame) -> pd.DataFrame:
    """各台風の勝者ノード（BMU）を求めてmetaに付与する。"""
    winners = [som.winner(f) for f in features]
    meta = meta.copy()
    meta["node"] = [f"{r}-{c}" for r, c in winners]
    meta["node_row"] = [r for r, c in winners]
    meta["node_col"] = [c for r, c in winners]
    return meta


def node_color(row: int, col: int, n_rows: int, n_cols: int) -> tuple:
    """SOMグリッド上の位置をHSV色空間に写した固有色を返す。

    隣接ノード（似た進路パターン）が似た色になるようにし、代表経路の地図と
    月別出現比率グラフで同じ配色を使うことでノード間の対応を追いやすくする。
    """
    import matplotlib.colors as mcolors

    hue = row / n_rows  # n_rowsで割り、hue=1.0（赤に戻る）に達しないようにする
    value = 0.55 + 0.45 * col / max(n_cols - 1, 1)
    return tuple(mcolors.hsv_to_rgb([hue, 0.75, value]))


def plot_node_representative_tracks(som: MiniSom, out_path: Path) -> None:
    """各SOMノードの重みベクトルを代表経路として東アジア地図に描画する。"""
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature

    n_rows, n_cols = SOM_SHAPE
    fig, axes = plt.subplots(
        n_rows, n_cols, figsize=(4 * n_cols, 3.5 * n_rows),
        subplot_kw={"projection": ccrs.PlateCarree()},
    )

    weights = som.get_weights()  # shape (n_rows, n_cols, 2*N_RESAMPLE)
    for r in range(n_rows):
        for c in range(n_cols):
            ax = axes[r, c]
            ax.set_extent(MAP_EXTENT, crs=ccrs.PlateCarree())
            ax.add_feature(cfeature.LAND, facecolor="0.9")
            ax.add_feature(cfeature.COASTLINE, linewidth=0.5)

            color = node_color(r, c, n_rows, n_cols)
            vec = weights[r, c]
            lat = vec[:N_RESAMPLE]
            lon = vec[N_RESAMPLE:]
            ax.plot(lon, lat, transform=ccrs.PlateCarree(), color=color, linewidth=2.5)
            ax.plot(lon[0], lat[0], "o", transform=ccrs.PlateCarree(), color="green", markersize=4)
            ax.plot(lon[-1], lat[-1], "s", transform=ccrs.PlateCarree(), color="red", markersize=4)
            for spine in ax.spines.values():
                spine.set_edgecolor(color)
                spine.set_linewidth(3)
            ax.set_title(f"node ({r},{c})", fontsize=9)

    fig.suptitle(
        "SOMノード別 代表進路パターン（緑=発生, 赤=消滅/終端、枠色=下図と対応）", fontsize=16
    )
    fig.tight_layout()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"出力: {out_path}")


def plot_monthly_node_composition(meta: pd.DataFrame, out_path: Path) -> None:
    """月別・ノード別の出現比率を積み上げ棒グラフで可視化する。"""
    n_rows, n_cols = SOM_SHAPE
    node_order = [f"{r}-{c}" for r in range(n_rows) for c in range(n_cols)]
    colors = [node_color(r, c, n_rows, n_cols) for r in range(n_rows) for c in range(n_cols)]

    counts = meta.groupby(["origin_month", "node"]).size().unstack(fill_value=0)
    counts = counts.reindex(columns=node_order, fill_value=0)
    ratios = counts.div(counts.sum(axis=1), axis=0)
    ratios = ratios.reindex(range(1, 13), fill_value=0)

    fig, ax = plt.subplots(figsize=(14, 7))
    ratios.plot(kind="bar", stacked=True, ax=ax, color=colors, width=0.8)
    ax.set_xlabel("発生月")
    ax.set_ylabel("ノード別出現比率")
    ax.set_title("月別 SOMノード出現比率（台風進路パターンの季節傾向）")
    ax.legend(title="node", bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=8, ncol=2)
    ax.set_xticklabels([f"{m}月" for m in range(1, 13)], rotation=0)
    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    print(f"出力: {out_path}")


if __name__ == "__main__":
    df = pd.read_csv(DATA_PROCESSED_DIR / "best_track.csv", parse_dates=["datetime"])
    features, meta = build_feature_matrix(df)
    print(f"特徴ベクトル数: {len(features)}（除外: {df['international_id'].nunique() - len(features)}件）")

    som = train_som(features)
    meta = assign_nodes(som, features, meta)
    meta.to_csv(DATA_PROCESSED_DIR / "som_assignment.csv", index=False)
    print(f"ノード割当を保存: {DATA_PROCESSED_DIR / 'som_assignment.csv'}")

    plot_node_representative_tracks(som, OUTPUT_DIR / "phase2_som_node_tracks.png")
    plot_monthly_node_composition(meta, OUTPUT_DIR / "phase2_monthly_node_composition.png")

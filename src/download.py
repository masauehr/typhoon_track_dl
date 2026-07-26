"""気象庁RSMC東京 台風ベストトラックデータ（テキスト形式）のダウンロード。

出典: 気象庁 RSMC東京－台風センター
      https://www.jma.go.jp/jma/jma-eng/jma-center/rsmc-hp-pub-eg/besttrack.html

グローバルCLAUDE.mdのセキュリティルールにより curl / wget は使用せず、
Pythonの requests ライブラリでダウンロードする。
"""
import zipfile
from pathlib import Path

import requests

BEST_TRACK_ALL_URL = (
    "https://www.jma.go.jp/jma/jma-eng/jma-center/rsmc-hp-pub-eg/"
    "Besttracks/bst_all.zip"
)

DATA_RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"


def download_best_track_all(dest_dir: Path = DATA_RAW_DIR) -> Path:
    """全期間（1951年〜現在）のベストトラックzipをダウンロードし、解凍する。

    Returns:
        解凍後のテキストファイルのパス
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dest_dir / "bst_all.zip"

    response = requests.get(BEST_TRACK_ALL_URL, timeout=30)
    response.raise_for_status()
    zip_path.write_bytes(response.content)

    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest_dir)
        extracted_names = zf.namelist()

    print(f"ダウンロード完了: {zip_path}")
    print(f"展開されたファイル: {extracted_names}")

    return dest_dir / extracted_names[0]


if __name__ == "__main__":
    download_best_track_all()

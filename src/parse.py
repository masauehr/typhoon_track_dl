"""気象庁RSMC東京 台風ベストトラックデータ（固定長テキスト）のパーサー。

フォーマットは公式仕様書（e_format_bst.html）に基づくが、桁位置は
実データ（data/raw/bst_all.txt）に対する目視照合で確定させたもの
（テキストのフィールド区切りが仕様書の記載と実データで一部食い違うため）。

ヘッダー行（'66666'始まり、1行=1台風）:
    pos 1-5   : インジケータ '66666'
    pos 7-10  : 国際番号ID（下2桁=年、下2桁=その年の通し番号）
    pos 13-15 : データ行数
    pos 31-50 : 台風名（右詰め、命名前は空白）
    pos 65-72 : 最終更新日（yyyymmdd）

データ行（1行=6時間毎の1観測点）:
    pos 1-8   : 日時 yymmddhh（UTC）
    pos 14    : グレード（強度階級）
    pos 16-18 : 緯度（0.1度単位）
    pos 20-23 : 経度（0.1度単位）
    pos 25-28 : 中心気圧（hPa）
    pos 34-36 : 最大風速（kt、1977年以降のみ記録。それ以前は'000'）
"""
from pathlib import Path

import pandas as pd

DATA_RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
DATA_PROCESSED_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

GRADE_LABELS = {
    2: "TD",   # 熱帯低気圧
    3: "TS",   # 熱帯低気圧(TS)
    4: "STS",  # 強い熱帯低気圧
    5: "TY",   # 台風
    6: "L",    # 温帯低気圧
    7: "ENTERING",  # 東京責任域への進入時
    9: "TS_OR_ABOVE",  # TS以上（風速データ整備以前の簡易分類）
}


def _year_from_2digit(yy: int) -> int:
    """2桁年を4桁年に変換する（本データの対象年は1951年〜のため pivot=50）。"""
    return 1900 + yy if yy >= 51 else 2000 + yy


def parse_best_track(path: Path) -> pd.DataFrame:
    """固定長ベストトラックテキストを読み込み、観測点単位のDataFrameに変換する。

    Returns:
        columns: international_id, name, datetime, grade, grade_label,
                 lat, lon, pressure, max_wind
    """
    records = []
    current_id = None
    current_name = None

    with open(path, encoding="ascii") as f:
        for line in f:
            if line.startswith("66666"):
                current_id = line[6:10].strip()
                current_name = line[30:50].strip()
                continue

            yy = int(line[0:2])
            mm = int(line[2:4])
            dd = int(line[4:6])
            hh = int(line[6:8])
            grade = int(line[13:14])
            lat = int(line[15:18]) / 10.0
            lon = int(line[19:23]) / 10.0
            pressure = int(line[24:28])
            wind_field = line[33:36].strip()
            max_wind = int(wind_field) if wind_field else None
            if max_wind == 0:
                max_wind = None

            year = _year_from_2digit(yy)
            records.append(
                {
                    "international_id": current_id,
                    "name": current_name,
                    "datetime": pd.Timestamp(year, mm, dd, hh, tz="UTC"),
                    "grade": grade,
                    "grade_label": GRADE_LABELS.get(grade, "UNKNOWN"),
                    "lat": lat,
                    "lon": lon,
                    "pressure": pressure,
                    "max_wind": max_wind,
                }
            )

    return pd.DataFrame.from_records(records)


if __name__ == "__main__":
    df = parse_best_track(DATA_RAW_DIR / "bst_all.txt")
    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_PROCESSED_DIR / "best_track.csv"
    df.to_csv(out_path, index=False)
    print(f"観測点数: {len(df)}")
    print(f"台風数: {df['international_id'].nunique()}")
    print(f"出力: {out_path}")
    print(df.head())

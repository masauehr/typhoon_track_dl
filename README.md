# typhoon_track_dl

気象庁ベストトラックデータを用いて、東アジアにおける台風進路の月毎の傾向を
深層学習（自己組織化マップ等）で探究するプロジェクト。

詳しくは [MANUAL.md](MANUAL.md) / [typhoon-track-dl.md](typhoon-track-dl.md)（pc_docs運用マニュアルのコピー）を参照。

## 概要

- 気象庁RSMC東京の台風ベストトラックデータ（緯度・経度・中心気圧・最大風速の6時間毎時系列、1951年〜現在）を使用。
- 「進路図の画像」ではなく、公式に構造化された数値データを直接扱う方針（詳細は[MANUAL.md](MANUAL.md)参照）。
- Self-Organizing Map（SOM）による教師なしクラスタリングで進路パターンを分類し、
  月ごとの出現傾向を可視化することが本命のアプローチ。
- 実現可能性が未知数の探究的プロジェクトのため、まず古典的な可視化・統計で妥当性を確認してから
  深層学習的手法に進む段階的な進め方を取る。

## 進め方（サマリー）

1. データ取得・前処理（IBTrACS または気象庁ベストトラックテキスト）
2. 月別の目視・統計による傾向確認（ベースライン）
3. SOMによる進路パターンのクラスタリング・月別集計（本命）
4. （発展）系列オートエンコーダとの比較検証

## ディレクトリ構成

```
typhoon_track_dl/
├── README.md          # このファイル
├── CLAUDE.md          # Claude Code向けプロジェクト固有ルール
├── MANUAL.md          # 手法・進め方の詳細
├── requirements.txt   # 依存パッケージ（Phaseごとにコメントで区分）
├── src/
│   ├── download.py         # 気象庁ベストトラックzipのダウンロード
│   ├── parse.py            # 固定長テキストのパース → data/processed/best_track.csv
│   └── visualize_monthly.py # Phase1: 月別台風トラックの地図可視化
├── data/
│   ├── raw/            # ダウンロードした生データ（git管理外）
│   └── processed/      # パース済みCSV（git管理外）
├── outputs/            # 可視化結果（画像）
└── notebooks/          # 検証用notebook
```

## セットアップ・実行方法

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

.venv/bin/python src/download.py          # data/raw/bst_all.txt を取得
.venv/bin/python src/parse.py             # data/processed/best_track.csv を生成
.venv/bin/python src/visualize_monthly.py # outputs/phase1_monthly_tracks.png を生成
```

## Phase1: 月別台風進路（古典的検証）

発生月（最初の観測点の月）ごとに全台風のトラックを東アジア地図に重ね書きした結果:

![月別台風進路](outputs/phase1_monthly_tracks.png)

既知の季節傾向とよく整合することを確認:
- **7-8月**（台風数最多期）: 太平洋高気圧の縁を回るように日本近海へ直進する経路が密集。
- **9-10月**: フィリピン近海で発生し、偏西風帯に入って東へ再カーブする経路が明瞭に増加。
- **11-3月**（台風数最少期）: 発生位置が低緯度側にシフトし、日本まで北上せず南シナ海方面へ
  向かう経路が主流。

## ステータス

2026-07-26 Phase1（古典的検証）完了。月別台風進路の可視化が既知の季節傾向と
整合することを確認したため、Phase2（SOMクラスタリング）に進める見込み。

2026-07-26 Phase0（データ取得・前処理）実装完了。
気象庁RSMC東京のベストトラック全期間データ（1951〜2026年、台風1955個・
観測点71223件）をダウンロード・パースするスクリプトを実装。
令和元年東日本台風（HAGIBIS, 国際番号1919）の最盛期記録
（中心気圧915hPa・最大風速105kt）が気象庁公表値と一致することを確認済み。

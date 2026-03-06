# andersan-grid

airpollutionwatch-api から取得した大気観測データ（測定局ごとの同時観測量）を空間内挿し、任意地点および 2D グリッド上での値を推定・可視化するための Python CLI ツールです。

- 全国データの取得に2秒、地理院タイル(12)で全国をカバーしてフィッティングするのに3秒。

現状の機能（プロトタイプ段階）:

- `airpollutionwatch` API（[ai-docs](http://andersan.net:8089/v1/meta/ai-docs) 参照）から 1 時刻スナップショットを取得し、CSV に保存
- 1 時刻スナップショットの観測点データ（CSV）を入力として読み込み
- 全ての観測量（汚染物質など）を対象に
    - ガウス過程回帰（GPR）による内挿
    - 線形補間（scipy.interpolate.griddata の linear）による内挿
- 2D グリッド上のヒートマップ画像（PNG）を出力し、手法間の結果の違いを比較可能

## セットアップ

```bash
# venv を自分で作る場合
python -m venv .venv
source .venv/bin/activate  # Windows の場合は .venv\\Scripts\\activate
pip install -r requirements.txt
```

### Poetry を使う場合

このリポジトリには `pyproject.toml` を用意してあるので、Poetry で仮想環境を作成して利用できます（仮想環境の作成自体はユーザー側で実行してください）。

```bash
# （任意）プロジェクト内に .venv を作りたい場合
poetry config virtualenvs.in-project true

# 依存関係のインストールと仮想環境の作成
poetry install

# CLI の実行例
poetry run andersan-grid fetch --help
poetry run andersan-grid interpolate --help
```

## 想定するワークフロー（現時点）

1. `fetch` サブコマンドで、airpollutionwatch API から 1 時刻スナップショットを取得して CSV を作成する
    - 例:
        ```bash
        python -m andersan_grid.cli fetch \
          --pref tokyo \
          --target-datetime 2024-09-03T06:00:00+09:00 \
          --pollutants pm25,ox,no2 \
          --output data/tokyo_20240903T0600.csv
        ```
2. `interpolate` サブコマンドで、上記 CSV を 2D グリッドに内挿し、GPR と線形補間の結果を PNG として出力する
    - 必須列: `station_id`, `lon`, `lat`
    - 汚染物質などの観測量は、それ以外の数値列として扱う（例: `PM25`, `NO2`, `O3`, ...）
    - 例:
        ```bash
        python -m andersan_grid.cli interpolate \
          --input data/tokyo_20240903T0600.csv \
          --out-dir outputs/tokyo_20240903T0600 \
          --method gpr linear \
          --resolution-deg 0.05
        ```
3. 生成されたヒートマップ PNG を見比べて、手法ごとの差異や GPR の不確実性（標準偏差マップ）を確認する

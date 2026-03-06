# andersan-grid API 仕様

## 概要

大気汚染観測局の測定値を空間補間し、地理院タイル座標系でグリッド化した値を提供する API。
airpollutionwatch (APW) API の `/v1/` 名前空間に統合することを前提とする。

補間アルゴリズムは Adaptive Thin Plate Spline (aTPS) をデフォルトとする。
TPS は O(N³) だが最適化ループがないため GPR に比べ大幅に軽量であり、
APW サーバへの負荷は許容範囲内と判断する。

### 統合アーキテクチャ（採用方針）

```
APW DB への書きこみ
  └─→ 補間トリガ（同一プロセス or 非同期ワーカー）
        └─→ 全国一括補間（TPS、< 5 秒 @ z=12）
              └─→ グリッドキャッシュ更新
                    └─→ /v1/grid/* で提供
```

APW DB に直接アクセスできるため、API 経由のデータ取得オーバーヘッドが不要。
DB 書きこみタイミングで補間するため、5 分ごとのポーリングも不要。

### 別個サーバとして運用する場合（参考）

APW API を 5 分ごとにポーリングし、いずれかの観測局のタイムスタンプが
更新されていれば全国補間を再実行してキャッシュを更新する。

---

## データの鮮度について

APW は各観測局のデータ取得完了まで最大 15 分程度かかる。
全国一括取得では一部の局が古いデータのまま混在する可能性がある。
このため、すべてのレスポンスには以下を含む：

- `grid_generated_at`: このグリッドキャッシュが生成された時刻
- `apw_snapshot_at`: APW から取得したスナップショットの基準時刻
- `apw_oldest_station_at`: そのスナップショット内で最も古い観測局のタイムスタンプ

---

## エンドポイント

ベースパス: `/v1/grid`

---

### GET `/v1/grid/snapshot` — タイル点スナップショット

指定したタイル座標群における、ある時刻の補間値を返す。
airpollutionwatch の `GET /v1/measurements?format=snapshot` に相当。

#### リクエストパラメータ

| パラメータ | 型 | 必須 | 説明 |
|---|---|---|---|
| `z` | int | ○ | ズームレベル（推奨: 12 または 14） |
| `tiles` | string | ○ | `x,y` ペアをセミコロン区切り。例: `3630,1620;3631,1620` |
| `pollutants` | string | ○ | カンマ区切り。例: `no2,ox,pm25` |
| `datetime` | string | ○ | ISO 8601。例: `2026-03-06T12:00:00+09:00` |
| `method` | string | — | 補間手法。デフォルト: `atps` |

#### レスポンス

```json
{
  "datetime": "2026-03-06T12:00:00+09:00",
  "z": 12,
  "method": "atps",
  "grid_generated_at": "2026-03-06T12:04:37+09:00",
  "apw_snapshot_at":   "2026-03-06T12:00:00+09:00",
  "apw_oldest_station_at": "2026-03-06T11:55:00+09:00",
  "tiles": [
    { "x": 3630, "y": 1620, "no2": 18.3, "ox": 42.1, "pm25": 9.4 },
    { "x": 3631, "y": 1620, "no2": 15.7, "ox": 38.6, "pm25": 8.1 }
  ]
}
```

---

### GET `/v1/grid/timeseries` — タイル点時系列

指定したタイル座標群における、時間範囲の補間値時系列を返す。

#### リクエストパラメータ

| パラメータ | 型 | 必須 | 説明 |
|---|---|---|---|
| `z` | int | ○ | ズームレベル |
| `tiles` | string | ○ | `x,y` ペアをセミコロン区切り |
| `pollutants` | string | ○ | カンマ区切り |
| `from` | string | ○ | 開始時刻（ISO 8601） |
| `to` | string | ○ | 終了時刻（ISO 8601） |
| `interval` | string | — | 集計間隔。デフォルト: `1h`。例: `30m`, `1h`, `3h` |
| `method` | string | — | デフォルト: `atps` |

#### レスポンス

```json
{
  "z": 12,
  "method": "atps",
  "from": "2026-03-06T00:00:00+09:00",
  "to":   "2026-03-06T23:00:00+09:00",
  "interval": "1h",
  "tiles": [
    {
      "x": 3630, "y": 1620,
      "series": [
        {
          "datetime": "2026-03-06T00:00:00+09:00",
          "grid_generated_at": "2026-03-06T00:04:12+09:00",
          "no2": 12.1, "ox": 55.3, "pm25": 7.8
        },
        {
          "datetime": "2026-03-06T01:00:00+09:00",
          "grid_generated_at": "2026-03-06T01:03:58+09:00",
          "no2": 11.8, "ox": 54.0, "pm25": 7.5
        }
      ]
    }
  ]
}
```

---

### GET `/v1/grid/field` — 全タイルフィールド（地図描画用）

指定した bbox 内の全タイル補間値を返す。
Web 地図への等値線描画やタイル色付けに使用する。

#### リクエストパラメータ

| パラメータ | 型 | 必須 | 説明 |
|---|---|---|---|
| `z` | int | ○ | ズームレベル |
| `pollutant` | string | ○ | 1 つの観測量 |
| `datetime` | string | ○ | ISO 8601 |
| `bbox` | string | — | `min_lon,min_lat,max_lon,max_lat`。省略時は全国 |
| `method` | string | — | デフォルト: `atps` |

#### レスポンス

```json
{
  "datetime": "2026-03-06T12:00:00+09:00",
  "z": 12,
  "pollutant": "no2",
  "method": "atps",
  "grid_generated_at": "2026-03-06T12:04:37+09:00",
  "tiles": [
    { "x": 3623, "y": 1605, "value": 8.2 },
    { "x": 3624, "y": 1605, "value": 9.1 }
  ]
}
```

---

### GET `/v1/grid/info` — メタ情報・キャッシュ状況

#### レスポンス

```json
{
  "available_zoom_levels": [12, 14],
  "default_method": "atps",
  "available_methods": ["atps", "tps", "linear", "gpr"],
  "pollutants": ["no2", "ox", "pm25"],
  "latest_grid_at": "2026-03-06T12:04:37+09:00",
  "latest_apw_snapshot_at": "2026-03-06T12:00:00+09:00",
  "cached_hours": 72
}
```

---

## キャッシュ戦略

- キャッシュキー: `(datetime_hour, z, method)` の組み合わせ
- 保持期間: 72 時間（設定可変）
- 全国 z=12 の補間は 1 時刻あたり約 5 秒で完了
- z=14 は約 30 秒（サーバスペックによる）
- キャッシュは SQLite または PostgreSQL テーブルとして永続化

---

## `method` パラメータ一覧

| 値 | 説明 |
|---|---|
| `atps` | 密度適応型 Thin Plate Spline（デフォルト・推奨） |
| `tps` | 一律 smoothing の Thin Plate Spline |
| `linear` | Delaunay 三角分割に基づく線形補間（凸包内のみ） |
| `gpr` | Gaussian Process Regression（不確実性付き、低速） |

GPR は `gpr_mean` / `gpr_std` として mean と standard deviation を別フィールドで返す。

---

## 未決事項

- `tiles` パラメータを GET クエリ文字列で渡す（タイル数上限は?）か、POST body にするか
- `gpr` の場合の `_std` フィールドをどの構造で返すか
- キャッシュストレージの選択（SQLite vs PostgreSQL）
- z=14 の全国補間をリアルタイムで行うか、オフラインバッチにするか

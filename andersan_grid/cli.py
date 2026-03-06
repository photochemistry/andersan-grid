from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from .api_client import AirPollutionWatchClient
from .grid import (
    BoundingBox,
    make_lonlat_grid,
    make_lonlat_grid_tiles,
)
from .interpolators import MethodName, interpolate_atps, interpolate_gpr, interpolate_linear, interpolate_tps
from .plotting import save_heatmap


def detect_pollutant_columns(df: pd.DataFrame) -> List[str]:
    """
    観測点データから、汚染物質などの「観測量」カラム名を推定する.

    station_id / lon / lat 以外の数値カラムを対象とする。
    """
    ignore = {
        "station_id",
        "station",
        "id",
        "lon",
        "lng",
        "longitude",
        "lat",
        "latitude",
    }
    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    return [c for c in numeric_cols if c not in ignore]


def run_interpolate(
    input_csv: Path,
    out_dir: Path,
    methods: List[MethodName],
    resolution_deg: float,
    bbox_margin_deg: float,
    tile_zoom: Optional[int] = None,
    gpr_local_scale_km: float = 20.0,
    gpr_regional_scale_km: float = 300.0,
    tps_smoothing: float = 1.0,
    atps_smoothing: float = 0.1,
    atps_k: int = 5,
) -> None:
    df = pd.read_csv(input_csv)

    # 必須列チェック
    if "lon" not in df.columns or "lat" not in df.columns:
        raise ValueError("入力 CSV には少なくとも 'lon', 'lat' 列が必要です。")

    lons = df["lon"].to_numpy(dtype=float)
    lats = df["lat"].to_numpy(dtype=float)

    # 座標が有効な局だけ bbox 計算に使う（NaN / 無限大 / 地理的にあり得ない値を除外）
    coord_valid = (
        np.isfinite(lons)
        & np.isfinite(lats)
        & (lons >= -180.0)
        & (lons <= 180.0)
        & (lats >= -90.0)
        & (lats <= 90.0)
    )
    if coord_valid.sum() == 0:
        raise ValueError("有効な座標（lon/lat）を持つ観測点が見つかりませんでした。")

    bbox = BoundingBox.from_points(
        lons[coord_valid], lats[coord_valid], margin=bbox_margin_deg
    )
    if tile_zoom is not None:
        lon2d, lat2d = make_lonlat_grid_tiles(bbox, zoom=tile_zoom)
    else:
        lon2d, lat2d = make_lonlat_grid(bbox, resolution_deg=resolution_deg)

    # 以降のどこかで in-place 書き換えが起きても地理座標を保持させる
    lon2d.flags.writeable = False
    lat2d.flags.writeable = False

    pollutant_cols = detect_pollutant_columns(df)
    if not pollutant_cols:
        raise ValueError("観測量となる数値カラムが見つかりませんでした。")

    out_dir.mkdir(parents=True, exist_ok=True)

    for col in pollutant_cols:
        values = df[col].to_numpy(dtype=float)

        # NaN / 無限大 / 地理的に不正な座標を含む点を除外
        valid_mask = (
            np.isfinite(values)
            & np.isfinite(lons)
            & np.isfinite(lats)
            & (lons >= -180.0)
            & (lons <= 180.0)
            & (lats >= -90.0)
            & (lats <= 90.0)
        )
        if valid_mask.sum() < 3:
            # 2D 補間には最低限の点数が必要なので、少なすぎる場合はスキップ
            print(
                f"[warn] 列 {col} は有効な観測点が少ないためスキップします (n_valid={valid_mask.sum()})."
            )
            continue

        lons_valid = lons[valid_mask]
        lats_valid = lats[valid_mask]
        values_valid = values[valid_mask]

        vmin = float(np.nanpercentile(values_valid, 5))
        vmax = float(np.nanpercentile(values_valid, 95))

        for method in methods:
            if method == "linear":
                field = interpolate_linear(
                    lons_valid, lats_valid, values_valid, lon2d, lat2d
                )
                title = f"{col} ({method})"
                out_path = out_dir / f"{col}_{method}.png"
                save_heatmap(
                    lon2d,
                    lat2d,
                    field,
                    title=title,
                    out_path=out_path,
                    vmin=vmin,
                    vmax=vmax,
                    station_lon=lons_valid,
                    station_lat=lats_valid,
                    station_values=values_valid,
                )
            elif method == "gpr":
                mean_field, std_field = interpolate_gpr(
                    lons_valid,
                    lats_valid,
                    values_valid,
                    lon2d,
                    lat2d,
                    length_scale_local_km=gpr_local_scale_km,
                    length_scale_regional_km=gpr_regional_scale_km,
                )
                title_mean = f"{col} (gpr mean)"
                out_mean = out_dir / f"{col}_gpr_mean.png"
                save_heatmap(
                    lon2d,
                    lat2d,
                    mean_field,
                    title=title_mean,
                    out_path=out_mean,
                    vmin=vmin,
                    vmax=vmax,
                    station_lon=lons_valid,
                    station_lat=lats_valid,
                    station_values=values_valid,
                )

                title_std = f"{col} (gpr std)"
                out_std = out_dir / f"{col}_gpr_std.png"
                save_heatmap(
                    lon2d,
                    lat2d,
                    std_field,
                    title=title_std,
                    out_path=out_std,
                    cmap="magma",
                )
            elif method == "tps":
                field = interpolate_tps(
                    lons_valid, lats_valid, values_valid, lon2d, lat2d,
                    smoothing=tps_smoothing,
                )
                save_heatmap(
                    lon2d, lat2d, field,
                    title=f"{col} (tps)",
                    out_path=out_dir / f"{col}_tps.png",
                    vmin=vmin, vmax=vmax,
                    station_lon=lons_valid, station_lat=lats_valid,
                    station_values=values_valid,
                )
            elif method == "atps":
                field = interpolate_atps(
                    lons_valid, lats_valid, values_valid, lon2d, lat2d,
                    smoothing=atps_smoothing,
                    k=atps_k,
                )
                save_heatmap(
                    lon2d, lat2d, field,
                    title=f"{col} (atps)",
                    out_path=out_dir / f"{col}_atps.png",
                    vmin=vmin, vmax=vmax,
                    station_lon=lons_valid, station_lat=lats_valid,
                    station_values=values_valid,
                )
            else:
                raise ValueError(f"未知の method: {method}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="andersan-grid",
        description="airpollutionwatch-api 等の観測点データを 2D グリッドに内挿して可視化するツール.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_interp = subparsers.add_parser(
        "interpolate",
        help="スナップショット CSV を読み込み、2D グリッドに内挿して PNG を出力する。",
    )
    p_interp.add_argument(
        "--input",
        type=Path,
        required=True,
        help="観測点スナップショットの CSV ファイルパス。",
    )
    p_interp.add_argument(
        "--out-dir",
        type=Path,
        required=True,
        help="出力 PNG を保存するディレクトリ。",
    )
    p_interp.add_argument(
        "--method",
        choices=["gpr", "linear", "tps", "atps"],
        nargs="+",
        default=["gpr", "linear", "tps", "atps"],
        help="使用する内挿手法（複数指定可）。atps は密度適応型 TPS。",
    )
    p_interp.add_argument(
        "--resolution-deg",
        type=float,
        default=0.05,
        help="グリッドの解像度 [deg]（経度・緯度方向）。--tile-zoom 指定時は無視されます。",
    )
    p_interp.add_argument(
        "--tile-zoom",
        type=int,
        help="地理院タイルのズームレベル（例: 12）。指定時は、その z のタイル中心に対応する緯度経度グリッドを生成します。",
    )
    p_interp.add_argument(
        "--bbox-margin-deg",
        type=float,
        default=0.1,
        help="観測点の最小・最大緯度経度に対して追加するマージン [deg]。",
    )
    p_interp.add_argument(
        "--gpr-local-scale",
        type=float,
        default=20.0,
        metavar="KM",
        help="GPR カーネルの短スケール [km]。都市内の局所変動を制御する。デフォルト: 20.0",
    )
    p_interp.add_argument(
        "--gpr-regional-scale",
        type=float,
        default=300.0,
        metavar="KM",
        help="GPR カーネルの長スケール [km]。疎な地域の地域トレンドを制御する。デフォルト: 300.0",
    )
    p_interp.add_argument(
        "--tps-smoothing",
        type=float,
        default=1.0,
        help="TPS の平滑化強度（全局一律）。0 で厳密補間。デフォルト: 1.0",
    )
    p_interp.add_argument(
        "--atps-smoothing",
        type=float,
        default=0.1,
        help="aTPS の基準平滑化強度（中央値密度の局に適用）。デフォルト: 0.1",
    )
    p_interp.add_argument(
        "--atps-k",
        type=int,
        default=5,
        metavar="K",
        help="aTPS の密度推定に使う近傍局数。デフォルト: 5",
    )

    # airpollutionwatch からスナップショットを取得して CSV に保存するサブコマンド
    p_fetch = subparsers.add_parser(
        "fetch",
        help="airpollutionwatch API から 1 時刻スナップショットを取得し、CSV として保存する。",
    )
    p_fetch.add_argument(
        "--pref",
        required=True,
        help="対象とする都道府県 ID（例: tokyo, aichi）。",
    )
    p_fetch.add_argument(
        "--target-datetime",
        required=True,
        help="対象時刻 (ISO8601)。例: 2024-09-03T06:00:00+09:00",
    )
    p_fetch.add_argument(
        "--pollutants",
        help="取得する測定項目。pm25,ox,no2 などをカンマ区切りで指定。省略時は API のデフォルト。",
    )
    p_fetch.add_argument(
        "--output",
        type=Path,
        required=True,
        help="出力する CSV ファイルパス。",
    )
    p_fetch.add_argument(
        "--base-url",
        help="airpollutionwatch API のベース URL（既定: https://andersan.net:8089 または環境変数 AIRPOLLUTIONWATCH_BASE_URL）。",
    )

    return parser


def _extract_lon_lat_from_station(
    station: Dict,
) -> Tuple[Optional[float], Optional[float]]:
    """
    /v1/stations の各要素から経度・緯度を推定して取り出す.

    実際のキー名に依存しすぎないよう、典型的な候補を順に探す。
    """
    lon_keys = ["lon", "lng", "longitude", "lon_deg"]
    lat_keys = ["lat", "latitude", "lat_deg"]

    lon = None
    lat = None
    for k in lon_keys:
        if k in station:
            try:
                lon = float(station[k])
            except (TypeError, ValueError):
                pass
            break
    for k in lat_keys:
        if k in station:
            try:
                lat = float(station[k])
            except (TypeError, ValueError):
                pass
            break
    return lon, lat


def run_fetch(
    pref: str,
    target_datetime: str,
    pollutants: Optional[Sequence[str]],
    output: Path,
    base_url: Optional[str],
) -> None:
    """
    airpollutionwatch API から 1 時刻スナップショットを取得し、CSV に保存する.
    """
    client = AirPollutionWatchClient(base_url=base_url)

    # 局メタデータ（緯度経度など）
    stations = client.get_stations(pref=pref)
    station_meta: Dict[str, Dict[str, Optional[float]]] = {}
    for st in stations:
        station_id = str(st.get("station_id") or st.get("id") or "").strip()
        if not station_id:
            continue
        lon, lat = _extract_lon_lat_from_station(st)
        station_meta[station_id] = {"lon": lon, "lat": lat}

    # 観測値スナップショット
    items = client.get_snapshot_measurements(
        pref=pref, target_datetime=target_datetime, pollutants=pollutants
    )

    rows: List[Dict] = []
    pollutant_keys: set[str] = set()

    for item in items:
        station_id = str(item.get("station_id") or item.get("id") or "").strip()
        if not station_id:
            continue

        meta = station_meta.get(station_id, {})
        row: Dict = {
            "station_id": station_id,
            "lon": meta.get("lon"),
            "lat": meta.get("lat"),
        }

        # 測定値と思われる数値カラムを抽出（そらまめ互換列名など）
        for key, value in item.items():
            if key in {
                "station_id",
                "id",
                "pref",
                "target_datetime",
                "observed_datetime",
            }:
                continue
            if isinstance(value, (int, float)) or (
                isinstance(value, str) and value.replace(".", "", 1).isdigit()
            ):
                try:
                    row[key] = float(value)
                    pollutant_keys.add(key)
                except ValueError:
                    continue

        rows.append(row)

    if not rows:
        raise ValueError("取得したスナップショットに有効なレコードがありませんでした。")

    df = pd.DataFrame(rows)
    # station_id, lon, lat の順、その後に汚染物質カラムを並べる
    ordered_cols = ["station_id", "lon", "lat"] + sorted(pollutant_keys)
    existing_cols = [c for c in ordered_cols if c in df.columns]
    df = df[existing_cols]

    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "interpolate":
        methods: List[MethodName] = list(args.method)
        run_interpolate(
            input_csv=args.input,
            out_dir=args.out_dir,
            methods=methods,
            resolution_deg=args.resolution_deg,
            bbox_margin_deg=args.bbox_margin_deg,
            tile_zoom=args.tile_zoom,
            gpr_local_scale_km=args.gpr_local_scale,
            gpr_regional_scale_km=args.gpr_regional_scale,
            tps_smoothing=args.tps_smoothing,
            atps_smoothing=args.atps_smoothing,
            atps_k=args.atps_k,
        )
    elif args.command == "fetch":
        pollutants: Optional[List[str]] = None
        if args.pollutants:
            pollutants = [p.strip() for p in args.pollutants.split(",") if p.strip()]
        run_fetch(
            pref=args.pref,
            target_datetime=args.target_datetime,
            pollutants=pollutants,
            output=args.output,
            base_url=args.base_url,
        )
    else:
        parser.error(f"未知のコマンドです: {args.command}")


if __name__ == "__main__":
    main()

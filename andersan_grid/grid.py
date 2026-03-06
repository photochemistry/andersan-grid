from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import numpy as np


@dataclass
class BoundingBox:
    """緯度経度の矩形領域."""

    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

    @classmethod
    def from_points(
        cls, lons: np.ndarray, lats: np.ndarray, margin: float = 0.0
    ) -> "BoundingBox":
        """観測点から自動的に bbox を決める."""
        min_lon = float(np.min(lons)) - margin
        max_lon = float(np.max(lons)) + margin
        min_lat = float(np.min(lats)) - margin
        max_lat = float(np.max(lats)) + margin
        return cls(min_lon=min_lon, min_lat=min_lat, max_lon=max_lon, max_lat=max_lat)


def make_lonlat_grid(
    bbox: BoundingBox,
    resolution_deg: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    緯度経度空間で等間隔の 2D グリッドを生成する.

    Parameters
    ----------
    bbox:
        グリッド生成範囲.
    resolution_deg:
        経度・緯度方向の解像度 [deg].

    Returns
    -------
    lon2d, lat2d:
        shape (ny, nx) の 2D 配列.
    """
    lons = np.arange(bbox.min_lon, bbox.max_lon + resolution_deg * 0.5, resolution_deg)
    lats = np.arange(bbox.min_lat, bbox.max_lat + resolution_deg * 0.5, resolution_deg)
    lon2d, lat2d = np.meshgrid(lons, lats)
    return lon2d, lat2d



def lonlat_to_local_xy(
    lon: np.ndarray, lat: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """
    緯度経度を簡易的な局所直交座標 (km 単位) に変換する.

    観測領域が比較的狭いことを前提とし、GPR で扱いやすいスケールに変換する。
    """
    lon = np.asarray(lon, dtype=float)
    lat = np.asarray(lat, dtype=float)

    lon0 = float(np.mean(lon))
    lat0 = float(np.mean(lat))

    # 地球半径 ~ 6371 km, 1 deg あたりの距離を近似
    deg_to_km_lat = 111.32
    deg_to_km_lon = deg_to_km_lat * np.cos(np.deg2rad(lat0))

    x = (lon - lon0) * deg_to_km_lon
    y = (lat - lat0) * deg_to_km_lat
    return x, y


def lonlat_grid_to_local_xy(
    lon2d: np.ndarray,
    lat2d: np.ndarray,
    ref_lon: float,
    ref_lat: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    2D グリッドの緯度経度を、指定した基準点に対する局所座標 (km) に変換する.
    """
    deg_to_km_lat = 111.32
    deg_to_km_lon = deg_to_km_lat * np.cos(np.deg2rad(ref_lat))

    x = (lon2d - ref_lon) * deg_to_km_lon
    y = (lat2d - ref_lat) * deg_to_km_lat
    return x, y


def _webmercator_lonlat_to_tile_xy(
    lon: float, lat: float, zoom: int
) -> Tuple[float, float]:
    """地理院タイル（Web メルカトル）の連続タイル座標 (x, y) を返す."""
    n = 2.0**zoom
    x = (lon + 180.0) / 360.0 * n
    lat_rad = np.deg2rad(lat)
    y = (1.0 - np.log(np.tan(lat_rad) + 1.0 / np.cos(lat_rad)) / np.pi) / 2.0 * n
    return x, y


def _webmercator_tile_xy_to_lonlat(
    x: float, y: float, zoom: int
) -> Tuple[float, float]:
    """地理院タイル（Web メルカトル）のタイル座標 (x, y) からタイル中心の緯度経度を返す."""
    n = 2.0**zoom
    lon = x / n * 360.0 - 180.0
    lat_rad = np.arctan(np.sinh(np.pi * (1.0 - 2.0 * y / n)))
    lat = np.rad2deg(lat_rad)
    return lon, lat


def make_lonlat_grid_tiles(
    bbox: BoundingBox,
    zoom: int,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    地理院タイル（Web メルカトル）のタイル中心位置に対応する 2D グリッドを生成する.

    与えられた bbox を含むタイル範囲を計算し、そのタイル中心の緯度経度を格子として用いる。
    """
    if zoom < 0:
        raise ValueError("zoom は 0 以上の整数である必要があります。")

    # bbox をカバーするタイル範囲
    x_min_f, y_max_f = _webmercator_lonlat_to_tile_xy(bbox.min_lon, bbox.min_lat, zoom)
    x_max_f, y_min_f = _webmercator_lonlat_to_tile_xy(bbox.max_lon, bbox.max_lat, zoom)

    x_min = int(np.floor(min(x_min_f, x_max_f)))
    x_max = int(np.floor(max(x_min_f, x_max_f)))
    y_min = int(np.floor(min(y_min_f, y_max_f)))
    y_max = int(np.floor(max(y_min_f, y_max_f)))

    xs = np.arange(x_min, x_max + 1, dtype=float)
    ys = np.arange(y_min, y_max + 1, dtype=float)

    # タイル中心 (x+0.5, y+0.5) を緯度経度に変換
    lon_centers = []
    for xt in xs:
        lon, _ = _webmercator_tile_xy_to_lonlat(
            xt + 0.5, (y_min + y_max) / 2.0 + 0.5, zoom
        )
        lon_centers.append(lon)
    lon_centers = np.asarray(lon_centers, dtype=float)

    lat_centers = []
    for yt in ys:
        # 経度は任意で良いので中央付近の値を使用
        _, lat = _webmercator_tile_xy_to_lonlat(
            (x_min + x_max) / 2.0 + 0.5, yt + 0.5, zoom
        )
        lat_centers.append(lat)
    # ys は y_min→y_max（タイル y 軸は北が小さい）なので lat は降順（北→南）になる。
    # make_lonlat_grid と挙動を揃えるため、南→北（昇順）に反転する。
    lat_centers = np.asarray(lat_centers[::-1], dtype=float)

    lon2d, lat2d = np.meshgrid(lon_centers, lat_centers)
    return lon2d, lat2d

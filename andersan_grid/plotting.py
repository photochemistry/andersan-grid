from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import matplotlib.cm as mcm
import numpy as np


def save_heatmap(
    lon2d: np.ndarray,
    lat2d: np.ndarray,
    field: np.ndarray,
    *,
    title: str,
    out_path: Path,
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
    cmap: str = "viridis",
    station_lon: Optional[np.ndarray] = None,
    station_lat: Optional[np.ndarray] = None,
    station_values: Optional[np.ndarray] = None,
) -> None:
    """
    2D グリッド場のヒートマップを PNG として保存する.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # pcolormesh に渡す前に座標範囲を確定する（pcolormesh が配列を書き換える場合への対策）
    x_min, x_max = float(lon2d.min()), float(lon2d.max())
    y_min, y_max = float(lat2d.min()), float(lat2d.max())

    # NaN セルを透過にする（凸包外の未補間領域を表示しない）
    cmap_obj = mcm.get_cmap(cmap).copy()
    cmap_obj.set_bad(alpha=0.0)

    fig, ax = plt.subplots(figsize=(6, 5), constrained_layout=True)
    mesh = ax.pcolormesh(
        lon2d,
        lat2d,
        field,
        shading="auto",
        cmap=cmap_obj,
        vmin=vmin,
        vmax=vmax,
    )
    cbar = fig.colorbar(mesh, ax=ax)
    cbar.set_label("value")

    if station_lon is not None and station_lat is not None:
        ax.scatter(
            station_lon,
            station_lat,
            c=station_values,
            cmap=cmap,
            vmin=vmin,
            vmax=vmax,
            edgecolors="black",
            linewidths=0.5,
            s=30,
        )

    # pcolormesh と scatter が確実に同じ座標系に収まるよう、
    # pcolormesh 呼び出し前に取得した範囲を使う。
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)

    ax.set_xlabel("Longitude [deg]")
    ax.set_ylabel("Latitude [deg]")
    ax.set_title(title)

    fig.savefig(out_path, dpi=150)
    plt.close(fig)

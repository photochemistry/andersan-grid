from __future__ import annotations

from typing import Tuple

import numpy as np
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, WhiteKernel


def interpolate_gpr(
    lon: np.ndarray,
    lat: np.ndarray,
    values: np.ndarray,
    lon2d: np.ndarray,
    lat2d: np.ndarray,
    length_scale_local_km: float = 20.0,
    length_scale_regional_km: float = 300.0,
    noise_level: float = 0.1,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    ガウス過程回帰 (GPR) による空間内挿.

    マルチスケール RBF カーネルを使用する:
      - 短スケール (local):    都市内の局所変動を捉える
      - 長スケール (regional): 疎な地域でも観測局間を滑らかにつなぐ地域トレンドを捉える

    戻り値は (平均場, 標準偏差場)。
    """
    from andersan_grid.grid import lonlat_grid_to_local_xy, lonlat_to_local_xy

    x_obs, y_obs = lonlat_to_local_xy(lon, lat)
    X = np.column_stack([x_obs, y_obs])

    ref_lon = float(np.mean(lon))
    ref_lat = float(np.mean(lat))
    xg, yg = lonlat_grid_to_local_xy(lon2d, lat2d, ref_lon, ref_lat)
    Xg = np.column_stack([xg.ravel(), yg.ravel()])

    kernel = (
        RBF(
            length_scale=length_scale_local_km,
            length_scale_bounds=(5.0, 200.0),
        )
        + RBF(
            length_scale=length_scale_regional_km,
            length_scale_bounds=(100.0, 3000.0),
        )
        + WhiteKernel(noise_level=noise_level, noise_level_bounds=(1e-4, 1e1))
    )
    gpr = GaussianProcessRegressor(
        kernel=kernel,
        alpha=0.0,
        normalize_y=True,
        n_restarts_optimizer=2,
        random_state=0,
    )
    gpr.fit(X, values)

    mean, std = gpr.predict(Xg, return_std=True)
    mean_field = mean.reshape(lon2d.shape)
    std_field = std.reshape(lon2d.shape)
    return mean_field, std_field

"""空間内挿アルゴリズムパッケージ."""

from __future__ import annotations

from typing import Literal

from ._gpr import interpolate_gpr
from ._linear import interpolate_linear
from ._tps import interpolate_atps, interpolate_tps

MethodName = Literal["gpr", "linear", "tps", "atps"]

__all__ = [
    "MethodName",
    "interpolate_gpr",
    "interpolate_linear",
    "interpolate_tps",
    "interpolate_atps",
]

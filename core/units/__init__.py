"""Conversão de unidades com verificação dimensional (valores internos em SI)."""
from __future__ import annotations

import math

from core.exceptions import NexusError


class UnitError(NexusError):
    """Unidade desconhecida ou conversão dimensionalmente incompatível."""


# unidade -> (dimensão, fator para SI)
_UNITS: dict[str, tuple[str, float]] = {
    "m": ("length", 1.0), "cm": ("length", 1e-2), "mm": ("length", 1e-3),
    "kg": ("mass", 1.0), "g": ("mass", 1e-3),
    "s": ("time", 1.0), "ms": ("time", 1e-3),
    "rad": ("angle", 1.0), "deg": ("angle", math.pi / 180.0),
    "rad/s": ("angular_velocity", 1.0), "deg/s": ("angular_velocity", math.pi / 180.0),
    "rad/s2": ("angular_acceleration", 1.0), "deg/s2": ("angular_acceleration", math.pi / 180.0),
    "N": ("force", 1.0), "kN": ("force", 1e3),
    "N.m": ("torque", 1.0), "N.cm": ("torque", 1e-2), "N.mm": ("torque", 1e-3),
}


def dimension(unit: str) -> str:
    try:
        return _UNITS[unit][0]
    except KeyError:
        raise UnitError(f"Unidade desconhecida: {unit!r}") from None


def convert(value, from_unit: str, to_unit: str):
    """Converte value (escalar ou ndarray). Levanta UnitError se as dimensões diferirem."""
    d1, f1 = _UNITS.get(from_unit, (None, None))
    d2, f2 = _UNITS.get(to_unit, (None, None))
    if d1 is None:
        raise UnitError(f"Unidade desconhecida: {from_unit!r}")
    if d2 is None:
        raise UnitError(f"Unidade desconhecida: {to_unit!r}")
    if d1 != d2:
        raise UnitError(f"Dimensões incompatíveis: {from_unit} ({d1}) -> {to_unit} ({d2})")
    return value * (f1 / f2)


def deg2rad(x):
    return convert(x, "deg", "rad")


def rad2deg(x):
    return convert(x, "rad", "deg")

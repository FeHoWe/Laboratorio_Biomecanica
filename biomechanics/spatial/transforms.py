"""Transformações rígidas 4x4 (SE(3)). Reaproveita `core.geometry.transforms` e acrescenta utilitários espaciais."""
from __future__ import annotations

import numpy as np

from biomechanics.spatial.rotations import axis_angle_matrix, is_rotation
from core.geometry.transforms import apply, compose, homogeneous, invert, rot_x, rot_y, rot_z  # noqa: F401


def make(R=None, t=(0.0, 0.0, 0.0)) -> np.ndarray:
    return homogeneous(None if R is None else np.asarray(R, float), t)


def rotation(T: np.ndarray) -> np.ndarray:
    return T[:3, :3]


def translation(T: np.ndarray) -> np.ndarray:
    return T[:3, 3]


def apply_vector(T: np.ndarray, v) -> np.ndarray:
    """Aplica só a rotação (para vetores livres: eixos, forças, velocidades)."""
    return T[:3, :3] @ np.asarray(v, float)


def rotation_about(axis, angle: float, point=(0.0, 0.0, 0.0)) -> np.ndarray:
    """Rotação de `angle` em torno do eixo que passa por `point`."""
    R = axis_angle_matrix(axis, angle)
    p = np.asarray(point, float)
    return make(R, p - R @ p)


def translation_along(axis, distance: float) -> np.ndarray:
    a = np.asarray(axis, float)
    return make(None, a / np.linalg.norm(a) * distance)


def is_transform(T: np.ndarray, tol: float = 1e-9) -> bool:
    T = np.asarray(T, float)
    return bool(T.shape == (4, 4) and is_rotation(T[:3, :3], tol) and np.allclose(T[3], [0, 0, 0, 1], atol=tol))

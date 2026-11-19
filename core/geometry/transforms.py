"""Transformações geométricas: rotações e matrizes homogêneas 4x4 (SI, ângulos em rad)."""
from __future__ import annotations

import numpy as np


def rot_x(a: float) -> np.ndarray:
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=float)


def rot_y(a: float) -> np.ndarray:
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=float)


def rot_z(a: float) -> np.ndarray:
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=float)


def homogeneous(R: np.ndarray | None = None, t=(0.0, 0.0, 0.0)) -> np.ndarray:
    T = np.eye(4)
    if R is not None:
        T[:3, :3] = R
    T[:3, 3] = np.asarray(t, dtype=float)
    return T


def compose(*Ts: np.ndarray) -> np.ndarray:
    out = np.eye(4)
    for T in Ts:
        out = out @ T
    return out


def invert(T: np.ndarray) -> np.ndarray:
    """Inversa de transformação rígida (usa R^T, não inversão numérica geral)."""
    R, t = T[:3, :3], T[:3, 3]
    return homogeneous(R.T, -R.T @ t)


def apply(T: np.ndarray, p) -> np.ndarray:
    p = np.asarray(p, dtype=float)
    return T[:3, :3] @ p + T[:3, 3]


def is_rotation(R: np.ndarray, tol: float = 1e-9) -> bool:
    return bool(np.allclose(R @ R.T, np.eye(3), atol=tol) and abs(np.linalg.det(R) - 1.0) < tol)

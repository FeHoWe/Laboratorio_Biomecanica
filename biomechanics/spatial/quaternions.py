"""Quaternions unitários [w, x, y, z] (convenção de Hamilton) e conversões. q e −q representam a mesma rotação."""
from __future__ import annotations

import numpy as np

from biomechanics.spatial.rotations import RotationError, unit


def normalize(q) -> np.ndarray:
    q = np.asarray(q, float)
    n = np.linalg.norm(q)
    if not np.isfinite(n) or n < 1e-12:
        raise RotationError("Quaternion nulo ou não finito")
    return q / n


def identity() -> np.ndarray:
    return np.array([1.0, 0.0, 0.0, 0.0])


def conjugate(q) -> np.ndarray:
    q = np.asarray(q, float)
    return np.array([q[0], -q[1], -q[2], -q[3]])


def multiply(p, q) -> np.ndarray:
    """Produto de Hamilton p ⊗ q (aplica q primeiro, depois p, ao rotacionar vetores)."""
    w1, x1, y1, z1 = np.asarray(p, float)
    w2, x2, y2, z2 = np.asarray(q, float)
    return np.array([w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
                     w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
                     w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
                     w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2])


def inverse(q) -> np.ndarray:
    q = np.asarray(q, float)
    return conjugate(q) / float(q @ q)


def canonical(q) -> np.ndarray:
    """Escolhe o representante com w ≥ 0 (remove a ambiguidade de sinal)."""
    q = np.asarray(q, float)
    return -q if q[0] < 0 else q


def from_axis_angle(axis, angle: float) -> np.ndarray:
    a = unit(axis)
    return np.concatenate([[np.cos(angle / 2.0)], np.sin(angle / 2.0) * a])


def to_axis_angle(q) -> tuple[np.ndarray, float]:
    q = canonical(normalize(q))
    s = float(np.linalg.norm(q[1:]))
    if s < 1e-12:
        return np.array([0.0, 0.0, 1.0]), 0.0
    return q[1:] / s, float(2.0 * np.arctan2(s, q[0]))


def to_matrix(q) -> np.ndarray:
    w, x, y, z = normalize(q)
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def from_matrix(R: np.ndarray) -> np.ndarray:
    """Método de Shepperd (estável perto de rotações de 180°); retorna o representante com w ≥ 0."""
    R = np.asarray(R, float)
    tr = np.trace(R)
    if tr > 0:
        s = 2.0 * np.sqrt(tr + 1.0)
        q = [0.25 * s, (R[2, 1] - R[1, 2]) / s, (R[0, 2] - R[2, 0]) / s, (R[1, 0] - R[0, 1]) / s]
    elif R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = 2.0 * np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
        q = [(R[2, 1] - R[1, 2]) / s, 0.25 * s, (R[0, 1] + R[1, 0]) / s, (R[0, 2] + R[2, 0]) / s]
    elif R[1, 1] > R[2, 2]:
        s = 2.0 * np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
        q = [(R[0, 2] - R[2, 0]) / s, (R[0, 1] + R[1, 0]) / s, 0.25 * s, (R[1, 2] + R[2, 1]) / s]
    else:
        s = 2.0 * np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
        q = [(R[1, 0] - R[0, 1]) / s, (R[0, 2] + R[2, 0]) / s, (R[1, 2] + R[2, 1]) / s, 0.25 * s]
    return canonical(normalize(q))


def rotate(q, v) -> np.ndarray:
    """v' = q ⊗ (0, v) ⊗ q*."""
    qn = normalize(q)
    return multiply(multiply(qn, np.concatenate([[0.0], np.asarray(v, float)])), conjugate(qn))[1:]


def angle_between(p, q) -> float:
    """Menor ângulo de rotação (rad, em [0, π]) que leva p a q."""
    d = abs(float(np.clip(normalize(p) @ normalize(q), -1.0, 1.0)))
    return float(2.0 * np.arccos(d))


def slerp(p, q, t: float) -> np.ndarray:
    """Interpolação esférica pelo caminho mais curto."""
    p, q = normalize(p), normalize(q)
    d = float(p @ q)
    if d < 0:
        q, d = -q, -d
    if d > 0.9995:  # quase iguais: interpolação linear normalizada
        return normalize(p + t * (q - p))
    th = np.arccos(d)
    return (np.sin((1 - t) * th) * p + np.sin(t * th) * q) / np.sin(th)

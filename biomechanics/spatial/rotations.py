"""Rotações em SO(3): matrizes, eixo-ângulo (Rodrigues), logaritmo e ângulos de Euler (Tait-Bryan ZXY)."""
from __future__ import annotations

import numpy as np

from core.exceptions import NexusError
from core.geometry.transforms import is_rotation  # noqa: F401  (reexportado)


class RotationError(NexusError):
    pass


def unit(v, tol: float = 1e-12) -> np.ndarray:
    v = np.asarray(v, float)
    n = np.linalg.norm(v)
    if not np.isfinite(n) or n < tol:
        raise RotationError("Vetor nulo ou não finito: não define um eixo")
    return v / n


def skew(v) -> np.ndarray:
    x, y, z = np.asarray(v, float)
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])


def vee(S: np.ndarray) -> np.ndarray:
    return np.array([S[2, 1], S[0, 2], S[1, 0]])


def axis_angle_matrix(axis, angle: float) -> np.ndarray:
    """Fórmula de Rodrigues: R = I + sin(θ) K + (1 − cos θ) K²; o eixo é normalizado."""
    K = skew(unit(axis))
    return np.eye(3) + np.sin(angle) * K + (1.0 - np.cos(angle)) * (K @ K)


def matrix_log(R: np.ndarray, tol: float = 1e-9) -> tuple[np.ndarray, float]:
    """(eixo unitário, ângulo em [0, π]) tal que R = axis_angle_matrix(eixo, ângulo). Para ângulo 0 o eixo é z por convenção."""
    if not is_rotation(R, 1e-6):
        raise RotationError("Matriz não é uma rotação (R^T R ≠ I ou det ≠ 1)")
    c = float(np.clip((np.trace(R) - 1.0) / 2.0, -1.0, 1.0))
    v = vee(R - R.T) / 2.0                 # = sin(θ)·eixo
    sn = float(np.linalg.norm(v))
    ang = float(np.arctan2(sn, c))         # atan2 mantém precisão relativa para ângulos pequenos (arccos perde ~1e-8)
    if ang < min(tol, 1e-14) or sn < 1e-300:
        if c > 0:
            return np.array([0.0, 0.0, 1.0]), 0.0
    if np.pi - ang < 1e-6:  # perto de π: eixo a partir de R + I = 2 a a^T
        B = (R + np.eye(3)) / 2.0
        i = int(np.argmax(np.diag(B)))
        a = B[:, i] / np.sqrt(B[i, i])
        return unit(a), ang
    return v / sn, ang


def orthonormalize(R: np.ndarray) -> np.ndarray:
    """Projeta uma matriz quase-rotação em SO(3) (SVD), corrigindo deriva numérica."""
    U, _, Vt = np.linalg.svd(R)
    out = U @ Vt
    if np.linalg.det(out) < 0:
        U[:, -1] *= -1
        out = U @ Vt
    return out


def euler_zxy_to_matrix(a: float, b: float, c: float) -> np.ndarray:
    """R = Rz(a) Rx(b) Ry(c) (rotações intrínsecas: cada eixo no referencial já girado)."""
    return axis_angle_matrix([0, 0, 1], a) @ axis_angle_matrix([1, 0, 0], b) @ axis_angle_matrix([0, 1, 0], c)


def matrix_to_euler_zxy(R: np.ndarray, gimbal_tol: float = 1e-8) -> tuple[float, float, float, bool]:
    """Inverso de euler_zxy_to_matrix com b em [-π/2, π/2]. O quarto valor indica singularidade (|cos b| < tol):
    nesse caso c é fixado em 0 e a absorve a soma dos graus de liberdade restantes."""
    s = float(np.clip(R[2, 1], -1.0, 1.0))
    b = float(np.arcsin(s))
    if abs(np.cos(b)) < gimbal_tol:
        return float(np.arctan2(R[1, 0], R[0, 0])), b, 0.0, True
    return float(np.arctan2(-R[0, 1], R[1, 1])), b, float(np.arctan2(-R[2, 0], R[2, 2])), False

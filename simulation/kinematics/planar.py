"""Cinemática de cadeia planar de 2 segmentos (plano x-y, y para cima).

Convenção: q1 = ângulo absoluto do segmento 1 em relação ao eixo x;
q2 = ângulo relativo do segmento 2 em relação ao segmento 1 (rad).
Unidades: metros e radianos. Hipótese: corpos rígidos, juntas rotativas ideais.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core.exceptions import NexusError


class KinematicsError(NexusError):
    """Alvo inalcançável ou parâmetros inválidos."""


@dataclass(frozen=True)
class TwoLink:
    l1: float
    l2: float

    def __post_init__(self) -> None:
        if not (self.l1 > 0 and self.l2 > 0):
            raise KinematicsError("Comprimentos devem ser positivos (m)")

    def forward(self, q1: float, q2: float) -> dict:
        """Posições da junta intermediária (joelho/jarrete) e da extremidade."""
        joint = np.array([self.l1 * np.cos(q1), self.l1 * np.sin(q1)])
        tip = joint + self.l2 * np.array([np.cos(q1 + q2), np.sin(q1 + q2)])
        return {"joint": joint, "tip": tip}

    def inverse(self, x: float, y: float, elbow: str = "down") -> tuple[float, float]:
        """Solução analítica. elbow='down' -> q2 >= 0 ; 'up' -> q2 <= 0."""
        if elbow not in ("up", "down"):
            raise KinematicsError("elbow deve ser 'up' ou 'down'")
        r2 = x * x + y * y
        c2 = (r2 - self.l1**2 - self.l2**2) / (2 * self.l1 * self.l2)
        if c2 > 1 + 1e-12 or c2 < -1 - 1e-12:
            raise KinematicsError(
                f"Alvo ({x:.4f}, {y:.4f}) m fora do alcance [{abs(self.l1-self.l2):.4f}, {self.l1+self.l2:.4f}] m")
        c2 = float(np.clip(c2, -1.0, 1.0))
        q2 = float(np.arccos(c2)) * (1 if elbow == "down" else -1)
        q1 = float(np.arctan2(y, x) - np.arctan2(self.l2 * np.sin(q2), self.l1 + self.l2 * np.cos(q2)))
        return q1, q2

    def jacobian(self, q1: float, q2: float) -> np.ndarray:
        """J (2x2): d(tip)/d(q1,q2). Unidade: m/rad."""
        s1, c1 = np.sin(q1), np.cos(q1)
        s12, c12 = np.sin(q1 + q2), np.cos(q1 + q2)
        return np.array([[-self.l1 * s1 - self.l2 * s12, -self.l2 * s12],
                         [self.l1 * c1 + self.l2 * c12, self.l2 * c12]])


def min_jerk(q0: float, qf: float, T: float, n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Trajetória de mínimo jerk (polinômio quíntico) de q0 a qf em T s, n amostras.

    Devolve (t, q, qdot, qddot) analíticos; velocidade e aceleração nas bordas = 0.
    """
    if T <= 0 or n < 2:
        raise KinematicsError("T deve ser > 0 e n >= 2")
    t = np.linspace(0.0, T, n)
    s = t / T
    d = qf - q0
    q = q0 + d * (10 * s**3 - 15 * s**4 + 6 * s**5)
    qd = d * (30 * s**2 - 60 * s**3 + 30 * s**4) / T
    qdd = d * (60 * s - 180 * s**2 + 120 * s**3) / T**2
    return t, q, qd, qdd


def finite_diff(t: np.ndarray, q: np.ndarray) -> np.ndarray:
    """Derivada numérica (diferenças centrais; unilaterais nas bordas)."""
    return np.gradient(q, t, edge_order=2)

"""Velocidades e acelerações lineares/angulares de pontos de corpos rígidos de uma SpatialChain."""
from __future__ import annotations

import numpy as np

from biomechanics.spatial.spatial_chain import SpatialChain
from biomechanics.spatial.spatial_jacobian import body_point_jacobian


def velocity(chain: SpatialChain, q, qd, body: str, p_local) -> tuple[np.ndarray, np.ndarray]:
    """(v do ponto [m/s], ω do corpo [rad/s]) no mundo: v = Jv q̇, ω = Jw q̇."""
    Jv, Jw = body_point_jacobian(chain, q, body, p_local)
    qd = np.asarray(qd, float)
    return Jv @ qd, Jw @ qd


def jdot_qd(chain: SpatialChain, q, qd, body: str, p_local, h: float = 1e-6) -> tuple[np.ndarray, np.ndarray]:
    """J̇ q̇ = d/dt[J(q(t))] q̇ por diferença central ao longo de q̇ (erro O(h²))."""
    q, qd = np.asarray(q, float), np.asarray(qd, float)
    s = float(np.max(np.abs(qd)))
    if s < 1e-14:
        return np.zeros(3), np.zeros(3)
    step = h / s
    Jvp, Jwp = body_point_jacobian(chain, q + step * qd, body, p_local)
    Jvm, Jwm = body_point_jacobian(chain, q - step * qd, body, p_local)
    return (Jvp - Jvm) @ qd / (2 * step), (Jwp - Jwm) @ qd / (2 * step)


def acceleration(chain: SpatialChain, q, qd, qdd, body: str, p_local) -> tuple[np.ndarray, np.ndarray]:
    """(a do ponto [m/s²], α do corpo [rad/s²]): a = Jv q̈ + J̇v q̇, α = Jw q̈ + J̇w q̇."""
    Jv, Jw = body_point_jacobian(chain, q, body, p_local)
    dv, dw = jdot_qd(chain, q, qd, body, p_local)
    qdd = np.asarray(qdd, float)
    return Jv @ qdd + dv, Jw @ qdd + dw

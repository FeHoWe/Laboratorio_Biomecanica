"""Trajetórias 3D: mínimo jerk no espaço articular e em linha reta no espaço cartesiano (+ rastreamento por IK)."""
from __future__ import annotations

import numpy as np

from biomechanics.spatial.spatial_chain import SpatialChain
from core.exceptions import NexusError
from simulation.kinematics.planar import min_jerk
from simulation.spatial_kinematics.inverse import solve_ik


class TrajectoryError(NexusError):
    pass


def joint_min_jerk(q0, q1, duration: float, n: int):
    """(t, q, qd, qdd) com formas (n,), (n,m)... — quíntico por DOF (velocidade e aceleração nulas nas pontas)."""
    q0, q1 = np.asarray(q0, float), np.asarray(q1, float)
    if q0.shape != q1.shape:
        raise TrajectoryError("q0 e q1 devem ter o mesmo tamanho")
    cols = [min_jerk(a, b, duration, n) for a, b in zip(q0, q1)]
    t = cols[0][0]
    return t, np.column_stack([c[1] for c in cols]), np.column_stack([c[2] for c in cols]), np.column_stack([c[3] for c in cols])


def cartesian_line(p0, p1, duration: float, n: int):
    """Posição/velocidade/aceleração (n,3) ao longo do segmento p0→p1 com perfil de mínimo jerk."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    t, s, sd, sdd = min_jerk(0.0, 1.0, duration, n)
    d = p1 - p0
    return t, p0 + np.outer(s, d), np.outer(sd, d), np.outer(sdd, d)


def track_cartesian(chain: SpatialChain, body: str, p_local, positions, q0, **ik_kwargs):
    """Resolve IK em sequência (partida a quente). Retorna (q (n,dof), lista de IKResult). Levanta erro se algum ponto falhar."""
    q = np.asarray(q0, float)
    qs, results = [], []
    for i, p in enumerate(positions):
        r = solve_ik(chain, body, p_local, p, q, **ik_kwargs)
        if not r.converged:
            raise TrajectoryError(f"IK falhou no ponto {i}: {r.message}")
        q = r.q
        qs.append(q.copy())
        results.append(r)
    return np.array(qs), results

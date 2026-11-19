"""Jacobiano geométrico espacial.

Para um ponto P fixo no corpo b e o DOF k (eixo z_k, ponto do eixo o_k, ambos no mundo), na pose q:
  rotativo:    Jv[:,k] = z_k × (P − o_k),  Jw[:,k] = z_k
  prismático:  Jv[:,k] = z_k,              Jw[:,k] = 0
  DOFs que não movem b: coluna nula.   Então  v_P = Jv q̇,  ω_b = Jw q̇.
"""
from __future__ import annotations

import numpy as np

from biomechanics.spatial import transforms as T
from biomechanics.spatial.spatial_chain import FKResult, SpatialChain


def point_jacobian(chain: SpatialChain, fk: FKResult, body: str, p_world) -> tuple[np.ndarray, np.ndarray]:
    n = chain.n_dof
    Jv, Jw = np.zeros((3, n)), np.zeros((3, n))
    p = np.asarray(p_world, float)
    for k in chain.dof_path(body):
        z = fk.axis[k]
        if fk.kind[k] == "revolute":
            Jv[:, k] = np.cross(z, p - fk.origin[k])
            Jw[:, k] = z
        else:
            Jv[:, k] = z
    return Jv, Jw


def body_point_jacobian(chain: SpatialChain, q, body: str, p_local) -> tuple[np.ndarray, np.ndarray]:
    fk = chain.forward_kinematics(q)
    return point_jacobian(chain, fk, body, T.apply(fk.T[body], p_local))


def com_jacobian(chain: SpatialChain, q, body: str) -> tuple[np.ndarray, np.ndarray]:
    return body_point_jacobian(chain, q, body, chain.bodies[body].com)


def stacked_jacobian(chain: SpatialChain, q, body: str, p_local) -> np.ndarray:
    """J (6×n): linhas 0-2 = velocidade linear do ponto, 3-5 = velocidade angular do corpo."""
    Jv, Jw = body_point_jacobian(chain, q, body, p_local)
    return np.vstack([Jv, Jw])


def numerical_point_jacobian(chain: SpatialChain, q, body: str, p_local, h: float = 1e-6) -> np.ndarray:
    """Jv por diferenças centrais da posição (para validação)."""
    q = np.asarray(q, float)
    J = np.zeros((3, chain.n_dof))
    for k in range(chain.n_dof):
        qp, qm = q.copy(), q.copy()
        qp[k] += h
        qm[k] -= h
        pp = chain.point_world(body, p_local, chain.forward_kinematics(qp))
        pm = chain.point_world(body, p_local, chain.forward_kinematics(qm))
        J[:, k] = (pp - pm) / (2 * h)
    return J

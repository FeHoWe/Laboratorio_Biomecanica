"""Cinemática inversa numérica (mínimos quadrados amortecidos, DLS) para cadeias espaciais.

Passo: Δq = Jᵀ (J Jᵀ + λ² I)⁻¹ e, com e = [erro de posição; erro de orientação (vetor de rotação)] e λ adaptativo
(cresce quando o menor valor singular de J cai abaixo de ε → comportamento estável em singularidades).
Critério de convergência: ‖e_pos‖ < tol_pos e ‖e_rot‖ < tol_rot. Limites articulares são impostos por projeção (clamp).
Alcançabilidade: cota superior por desigualdade triangular (soma dos comprimentos de elos ao longo do caminho).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from biomechanics.spatial import transforms as T
from biomechanics.spatial.rotations import matrix_log
from biomechanics.spatial.spatial_chain import SpatialChain
from biomechanics.spatial.spatial_jacobian import point_jacobian


@dataclass
class IKResult:
    q: np.ndarray
    converged: bool
    iterations: int
    pos_error_m: float
    rot_error_rad: float
    message: str
    near_singular: bool = False
    clamped: bool = False


def reach_bound(chain: SpatialChain, body: str, p_local, include_prismatic: bool = True) -> float:
    """Distância máxima possível (m) entre a origem da base e o ponto, ao longo do caminho de juntas (cota superior)."""
    total = float(np.linalg.norm(chain.base_T[:3, 3] * 0.0))
    cur = body
    path_len = float(np.linalg.norm(np.asarray(p_local, float)))
    while cur != chain.base:
        j = chain.joints[chain.parent_joint[cur]]
        path_len += float(np.linalg.norm(j.origin_T()[:3, 3]))
        if include_prismatic:
            path_len += sum(max(abs(d.min), abs(d.max)) for d in j.dofs if d.kind == "prismatic")
        # o corpo pai contribui com o deslocamento de seu referencial até a próxima junta: já contado em origin_T
        cur = j.parent
    return total + path_len


def solve_ik(chain: SpatialChain, body: str, p_local, target_pos, q0=None, target_R=None, tol_pos: float = 1e-6,
             tol_rot: float = 1e-6, max_iter: int = 200, damping: float = 0.05, eps_sing: float = 0.05,
             max_step: float = 0.3, use_limits: bool = True) -> IKResult:
    q = np.array(chain.q if q0 is None else q0, float)
    chain.check_q(q)
    tp = np.asarray(target_pos, float)
    lo, hi = chain.limits()
    if use_limits:
        q = np.clip(q, lo, hi)
    base_pos = chain.base_T[:3, 3]
    dist, bound = float(np.linalg.norm(tp - base_pos)), reach_bound(chain, body, p_local)
    if dist > bound + tol_pos:
        return IKResult(q, False, 0, dist - bound, 0.0,
                        f"Alvo inalcançável: distância {dist:.4g} m da base excede o alcance máximo {bound:.4g} m")
    near_sing = clamped = False
    err_p = err_r = np.inf
    for it in range(1, max_iter + 1):
        fk = chain.forward_kinematics(q)
        p = T.apply(fk.T[body], p_local)
        Jv, Jw = point_jacobian(chain, fk, body, p)
        e_pos = tp - p
        if target_R is not None:
            ax, ang = matrix_log(np.asarray(target_R, float) @ fk.T[body][:3, :3].T)
            e_rot = ax * ang
            J, e = np.vstack([Jv, Jw]), np.concatenate([e_pos, e_rot])
        else:
            e_rot, J, e = np.zeros(3), Jv, e_pos
        err_p, err_r = float(np.linalg.norm(e_pos)), float(np.linalg.norm(e_rot))
        if err_p < tol_pos and err_r < tol_rot:
            return IKResult(q, True, it - 1, err_p, err_r, "Convergiu", near_sing, clamped)
        sv = np.linalg.svd(J, compute_uv=False)
        smin, smax = float(sv[-1]), float(sv[0])
        lam = damping
        if smin < eps_sing * max(smax, 1e-12):
            near_sing = True
            lam = max(lam, smax * (1.0 - smin / (eps_sing * max(smax, 1e-12))) * 0.5)
        dq = J.T @ np.linalg.solve(J @ J.T + lam ** 2 * np.eye(J.shape[0]), e)
        n = float(np.max(np.abs(dq)))
        if n > max_step:
            dq *= max_step / n
        q_new = q + dq
        if use_limits:
            c = np.clip(q_new, lo, hi)
            clamped = clamped or bool(np.any(c != q_new))
            q_new = c
        if np.max(np.abs(q_new - q)) < 1e-14:  # preso (limites/singularidade): para antes do limite de iterações
            break
        q = q_new
    msg = "Não convergiu: "
    msg += ("preso em limite articular ou singularidade" if np.max(np.abs(dq)) < 1e-12 or clamped
            else f"limite de {max_iter} iterações atingido") + f" (erro de posição {err_p:.3g} m, orientação {err_r:.3g} rad)"
    return IKResult(q, False, max_iter, err_p, err_r, msg, near_sing, clamped)

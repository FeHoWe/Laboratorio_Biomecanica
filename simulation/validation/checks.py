"""Verificações numéricas do motor espacial. Cada função devolve um dicionário com métricas e o veredito (bool)."""
from __future__ import annotations

import numpy as np

from biomechanics.spatial.spatial_dynamics import SpatialDynamics
from simulation.numerical_integrators.integrate import Trajectory


def mass_matrix_checks(dyn: SpatialDynamics, q) -> dict:
    M = dyn.mass_matrix(q)
    ev = np.linalg.eigvalsh(M)
    return {"symmetric": bool(np.allclose(M, M.T, atol=1e-12)), "min_eig": float(ev[0]), "positive_definite": bool(ev[0] > 0),
            "cond": float(ev[-1] / ev[0]) if ev[0] > 0 else float("inf")}


def passivity_check(dyn: SpatialDynamics, q, qd, h: float = 1e-6) -> float:
    """‖(Ṁ − 2C) + (Ṁ − 2C)ᵀ‖_max: deve ser ≈ 0 (Ṁ−2C antissimétrica)."""
    q, qd = np.asarray(q, float), np.asarray(qd, float)
    s = float(np.max(np.abs(qd))) or 1.0
    step = h / s
    Md = (dyn.mass_matrix(q + step * qd) - dyn.mass_matrix(q - step * qd)) / (2 * step)
    A = Md - 2 * dyn.coriolis_matrix(q, qd)
    return float(np.max(np.abs(A + A.T)))


def inverse_forward_consistency(dyn: SpatialDynamics, q, qd, qdd) -> float:
    tau = dyn.inverse_dynamics(q, qd, qdd)
    return float(np.max(np.abs(dyn.forward_dynamics(q, qd, tau) - np.asarray(qdd, float))))


def energy_drift(traj: Trajectory) -> dict:
    """Deriva relativa da energia mecânica (sistema conservativo): max|E−E0| / max(|E0|, ΔE_escala)."""
    scale = max(abs(float(traj.me[0])), float(np.ptp(traj.pe)), float(np.max(traj.ke)), 1e-12)
    d = float(np.max(np.abs(traj.me - traj.me[0])))
    return {"max_abs_drift_j": d, "relative": d / scale}


def work_energy_balance(traj: Trajectory) -> dict:
    """Trabalho dos torques ∫Στq̇ dt vs. variação de energia mecânica (sem cargas externas não conservativas)."""
    p = traj.power.sum(axis=1)
    W = float(np.sum(0.5 * (p[1:] + p[:-1]) * np.diff(traj.t)))
    dE = float(traj.me[-1] - traj.me[0])
    return {"work_j": W, "delta_energy_j": dE, "residual_j": abs(W - dE)}

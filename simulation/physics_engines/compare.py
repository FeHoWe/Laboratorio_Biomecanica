"""Comparação motor interno × MuJoCo para um BIO-003 (somente se MuJoCo estiver instalado; nada é inventado)."""
from __future__ import annotations

import numpy as np

from biomechanics.spatial.spatial_dynamics import SpatialDynamics
from research.experiments import bio003
from simulation.numerical_integrators.integrate import simulate
from simulation.physics_engines import mujoco_adapter as mj


def compare_bio003(params: bio003.Bio003Params) -> dict:
    """Roda a mesma condição inicial (sem torques; MuJoCo/RK4 e motor interno/RK4, mesmo passo) e devolve diferenças máximas."""
    params.validate()
    if any(abs(x) > 0 for x in list(params.tau_const_nm) + list(params.tau_amp_nm)):
        raise bio003.Bio003Error("A comparação com MuJoCo cobre apenas a dinâmica livre (torques nulos).")
    ch = bio003.build_chain(params)
    dyn = SpatialDynamics(ch, gravity=params.gravity_m_s2)
    q0, qd0 = np.radians(params.q0_deg), np.radians(params.qd0_deg_s)
    own = simulate(dyn, q0, qd0, params.duration_s, params.dt_s)
    model = mj.MujocoModel(ch, params.gravity_m_s2, params.dt_s, "RK4")
    t, q, qd = model.simulate(q0, qd0, params.duration_s)
    n = min(len(t), len(own.t))
    return {"mujoco_version": mj.version(), "samples": n, "max_abs_q_diff_rad": float(np.max(np.abs(q[:n] - own.q[:n]))),
            "max_abs_qd_diff_rad_s": float(np.max(np.abs(qd[:n] - own.qd[:n]))),
            "max_abs_mass_matrix_diff_q0": float(np.max(np.abs(model.mass_matrix(q0) - dyn.mass_matrix(q0)))),
            "max_abs_bias_diff_q0": float(np.max(np.abs(model.bias(q0, qd0) - dyn.coriolis_vector(q0, qd0) - dyn.gravity_vector(q0))))}

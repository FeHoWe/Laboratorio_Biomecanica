"""ETAPA 6 — adaptador MuJoCo opcional: comparação numérica com o motor interno (ignorado se MuJoCo não estiver instalado)."""
import numpy as np
import pytest

from biomechanics.human_model.spatial_lower_limb import build_spatial_lower_limb
from biomechanics.spatial.spatial_dynamics import SpatialDynamics
from simulation.physics_engines import mujoco_adapter as mj

RNG = np.random.default_rng(5)


def test_unavailable_path_is_honest(monkeypatch):
    monkeypatch.setattr(mj, "mujoco", None)
    assert not mj.available() and mj.version() == ""
    with pytest.raises(mj.MujocoUnavailable, match="não está instalado"):
        mj.MujocoModel(build_spatial_lower_limb())


pytestmark_mj = pytest.mark.skipif(not mj.available(), reason="MuJoCo não instalado")


@pytestmark_mj
def test_mjcf_has_expected_structure():
    ch = build_spatial_lower_limb()
    xml = mj.build_mjcf(ch)
    for name in ["pelvis", "femur", "tibia", "fibula", "foot"] + ch.dof_names():
        assert f'name="{name}"' in xml
    assert xml.count("<joint") == 6 and xml.count("<inertial") == 5


@pytestmark_mj
def test_forward_kinematics_com_and_mass_matrix_match_internal_engine():
    ch = build_spatial_lower_limb()
    dyn = SpatialDynamics(ch)
    model = mj.MujocoModel(ch)
    lo, hi = ch.limits()
    for _ in range(10):
        q = RNG.uniform(lo, hi)
        fk = ch.forward_kinematics(q)
        pos, com = model.body_positions(q), model.com_positions(q)
        for b in ("femur", "tibia", "fibula", "foot"):
            assert np.allclose(pos[b], fk.T[b][:3, 3], atol=1e-9), b
            assert np.allclose(com[b], ch.com_world(b, fk), atol=1e-9), b
        assert np.allclose(model.mass_matrix(q), dyn.mass_matrix(q), atol=1e-6)


@pytestmark_mj
def test_bias_and_inverse_dynamics_match_internal_engine():
    ch = build_spatial_lower_limb()
    dyn = SpatialDynamics(ch)
    model = mj.MujocoModel(ch)
    lo, hi = ch.limits()
    for _ in range(10):
        q, qd, qdd = RNG.uniform(lo * .8, hi * .8), RNG.uniform(-3, 3, 6), RNG.uniform(-5, 5, 6)
        mine_bias = dyn.coriolis_vector(q, qd) + dyn.gravity_vector(q)
        assert np.allclose(model.bias(q, qd), mine_bias, atol=1e-5)
        assert np.allclose(model.inverse_dynamics(q, qd, qdd), dyn.inverse_dynamics(q, qd, qdd), atol=1e-5)


@pytestmark_mj
def test_trajectory_and_energy_match_internal_engine():
    from simulation.numerical_integrators.integrate import simulate
    ch = build_spatial_lower_limb()
    dyn = SpatialDynamics(ch)
    q0, qd0 = np.radians([20, 5, 3, 30, 0, 2]), np.radians([10, 0, 5, -20, 0, 0])
    own = simulate(dyn, q0, qd0, 0.5, 0.0005)
    model = mj.MujocoModel(ch, timestep=0.0005)
    t, q, qd = model.simulate(q0, qd0, 0.5)
    assert np.allclose(q, own.q, atol=1e-5) and np.allclose(qd, own.qd, atol=1e-4)
    pe, ke = model.energy(q0, qd0)
    # MuJoCo inclui a pelve fixa na energia potencial (constante); o motor interno só os corpos móveis → compara descontando a pelve
    pelvis = ch.bodies["pelvis"]
    pe_pelvis = -pelvis.mass_kg * (dyn.g @ ch.com_world("pelvis", ch.forward_kinematics(q0)))
    assert np.isclose(pe - pe_pelvis, own.pe[0], atol=1e-6) and np.isclose(ke, own.ke[0], rtol=1e-6)


@pytestmark_mj
def test_compare_bio003_helper_and_refusal_with_torques():
    from research.experiments import bio003
    from simulation.physics_engines.compare import compare_bio003
    p = bio003.default_params()
    p.duration_s, p.dt_s = 0.3, 0.001
    r = compare_bio003(p)
    assert r["max_abs_q_diff_rad"] < 1e-5 and r["max_abs_mass_matrix_diff_q0"] < 1e-6 and r["max_abs_bias_diff_q0"] < 1e-5
    p.tau_const_nm[0] = 1.0
    with pytest.raises(bio003.Bio003Error, match="torques nulos"):
        compare_bio003(p)

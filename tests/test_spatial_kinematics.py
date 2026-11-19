"""ETAPA 2 — cinemática espacial: FK, Jacobiano (vs diferenças finitas), velocidades/acelerações, IK, trajetórias."""
import math

import numpy as np
import pytest

from biomechanics.human_model.lower_limb import LowerLimbModel
from biomechanics.human_model.spatial_lower_limb import DOF_NAMES, build_spatial_lower_limb
from biomechanics.spatial import transforms as T
from biomechanics.spatial.rigid_body import RigidBody, cylinder_inertia
from biomechanics.spatial.rotations import matrix_log
from biomechanics.spatial.spatial_chain import ChainError, SpatialChain
from biomechanics.spatial.spatial_jacobian import body_point_jacobian, numerical_point_jacobian, stacked_jacobian
from biomechanics.spatial.spatial_joints import fixed, prismatic, revolute
from simulation.kinematics.planar import TwoLink
from simulation.spatial_kinematics import kinematics as K
from simulation.spatial_kinematics.inverse import reach_bound, solve_ik
from simulation.spatial_kinematics.trajectories import TrajectoryError, cartesian_line, joint_min_jerk, track_cartesian

RNG = np.random.default_rng(7)


def body(bid, L=0.4, m=2.0, axis=0):
    d = [0, 0, 0]
    d[axis] = 1
    return RigidBody(bid, bid, L, m, [x * 0.5 * L for x in d], cylinder_inertia(m, L, 0.03, axis).tolist(),
                     {"shape": "cylinder", "radius_m": 0.03, "p0": [0, 0, 0], "p1": [x * L for x in d]})


def planar_arm(l1=0.5, l2=0.4):
    """2R no plano x-y (eixos z): coincide com TwoLink."""
    return SpatialChain("arm", [body("base"), body("l1", l1), body("l2", l2)],
                        [revolute("j1", "base", "l1", [0, 0, 1], [0, 0, 0], (-3.1, 3.1)),
                         revolute("j2", "l1", "l2", [0, 0, 1], [l1, 0, 0], (-3.1, 3.1))], "base")


def limb_q(rng=RNG):
    lo, hi = build_spatial_lower_limb().limits()
    return rng.uniform(lo * 0.6, hi * 0.6)


# ---------- estrutura ----------
def test_chain_structure_errors():
    b = [body("base"), body("a"), body("b")]
    with pytest.raises(ChainError, match="ordem|ciclo|conectado"):
        SpatialChain("x", b, [revolute("j2", "a", "b", [0, 0, 1], [0.4, 0, 0]), revolute("j1", "base", "a", [0, 0, 1], [0, 0, 0])], "base")
    with pytest.raises(ChainError, match="mais de uma junta"):
        SpatialChain("x", b, [revolute("j1", "base", "a", [0, 0, 1], [0, 0, 0]), revolute("j2", "base", "a", [0, 1, 0], [0, 0, 0])], "base")
    with pytest.raises(ChainError, match="sem junta"):
        SpatialChain("x", b, [revolute("j1", "base", "a", [0, 0, 1], [0, 0, 0])], "base")
    with pytest.raises(ChainError, match="duplicado"):
        SpatialChain("x", [body("a"), body("a")], [], "a")
    with pytest.raises(ChainError):
        SpatialChain("x", b, [], "inexistente")


# ---------- FK ----------
def test_fk_planar_arm_matches_planar_module():
    arm, ref = planar_arm(), TwoLink(0.5, 0.4)
    for _ in range(20):
        q = RNG.uniform(-2, 2, 2)
        fk = arm.forward_kinematics(q)
        tip = T.apply(fk.T["l2"], [0.4, 0, 0])
        jp = ref.forward(q[0], q[1])
        assert np.allclose(tip[:2], jp["tip"], atol=1e-12) and abs(tip[2]) < 1e-15
        assert np.allclose(fk.T["l2"][:3, 3][:2], jp["joint"], atol=1e-12)


def test_fk_axis_orientation_and_prismatic():
    ch = SpatialChain("c", [body("base"), body("a"), body("b")],
                      [revolute("j1", "base", "a", [0, 1, 0], [0, 0, 0], (-3, 3)), prismatic("p", "a", "b", [1, 0, 0], [0, 0, 0], (0, 1))], "base")
    fk = ch.forward_kinematics([math.pi / 2, 0.3])
    assert np.allclose(fk.T["b"][:3, 3], [0, 0, -0.3], atol=1e-12)   # x girado 90° em torno de y → −z
    assert np.allclose(fk.axis[1], [0, 0, -1], atol=1e-12) and fk.kind == ["revolute", "prismatic"]


def test_spatial_limb_matches_sagittal_model_for_random_poses():
    old, ch = LowerLimbModel(), build_spatial_lower_limb()
    assert ch.dof_names() == DOF_NAMES and ch.n_dof == 6
    for _ in range(30):
        h, k, a = (RNG.uniform(j.min_deg, j.max_deg) for j in (old.joints["hip"], old.joints["knee"], old.joints["ankle"]))
        for n, v in (("hip", h), ("knee", k), ("ankle", a)):
            old.set_angle(n, v)
        ref = old.forward_kinematics()
        q = np.radians([h, 0, 0, k, a, 0])
        fk = ch.forward_kinematics(q)
        assert np.allclose(fk.T["femur"][:3, 3], ref["hip"], atol=1e-12)
        assert np.allclose(fk.T["tibia"][:3, 3], ref["knee"], atol=1e-12)
        assert np.allclose(fk.T["foot"][:3, 3], ref["ankle"], atol=1e-12)
        assert np.allclose(T.apply(fk.T["foot"], [old.segments["foot"].length_m, 0, 0]), ref["toe"], atol=1e-12)
        for seg, (p0, p1) in old.segment_endpoints().items():
            if seg in ("femur", "tibia", "foot"):
                got = {"femur": ("femur", [0, -old.segments["femur"].length_m, 0]), "tibia": ("tibia", [0, -old.segments["tibia"].length_m, 0]),
                       "foot": ("foot", [old.segments["foot"].length_m, 0, 0])}[seg]
                assert np.allclose(T.apply(fk.T[got[0]], got[1]), p1, atol=1e-12)


def test_limb_total_com_matches_old_model_and_dict_roundtrip():
    old, ch = LowerLimbModel(), build_spatial_lower_limb()
    old.set_angle("hip", 40); old.set_angle("knee", 60); old.set_angle("ankle", -10)
    q = np.radians([40, 0, 0, 60, -10, 0])
    fk = ch.forward_kinematics(q)
    ids = ("femur", "tibia", "foot")   # o modelo antigo não tem fíbula (que desloca o CM em z): compara só os 3 segmentos comuns
    m = np.array([ch.bodies[i].mass_kg for i in ids])
    com = (m[:, None] * np.array([ch.com_world(i, fk) for i in ids])).sum(axis=0) / m.sum()
    assert np.allclose(com, old.total_com(), atol=1e-12)
    ch2 = SpatialChain.from_dict(ch.to_dict())
    assert np.allclose(ch2.forward_kinematics(q).T["foot"], ch.forward_kinematics(q).T["foot"]) and ch2.to_dict() == ch.to_dict()


# ---------- Jacobiano ----------
def test_jacobian_linear_part_matches_finite_differences():
    ch = build_spatial_lower_limb()
    for bid, p in (("foot", [0.24, 0, 0]), ("tibia", [0, -0.2, 0.01]), ("femur", ch.bodies["femur"].com_local_m), ("fibula", [0, -0.1, 0])):
        for _ in range(10):
            q = limb_q()
            Jv, _ = body_point_jacobian(ch, q, bid, p)
            assert np.allclose(Jv, numerical_point_jacobian(ch, q, bid, p), atol=1e-7), bid


def test_jacobian_angular_part_matches_finite_differences_of_rotation():
    ch = build_spatial_lower_limb()
    h = 1e-6
    for _ in range(10):
        q = limb_q()
        _, Jw = body_point_jacobian(ch, q, "foot", [0, 0, 0])
        R0 = ch.forward_kinematics(q).T["foot"][:3, :3]
        for k in range(ch.n_dof):
            qp = q.copy(); qp[k] += h
            ax, ang = matrix_log(ch.forward_kinematics(qp).T["foot"][:3, :3] @ R0.T)
            assert np.allclose(ax * ang / h, Jw[:, k], atol=1e-6)


def test_jacobian_columns_zero_for_dofs_that_do_not_move_body():
    ch = build_spatial_lower_limb()
    J = stacked_jacobian(ch, limb_q(), "femur", [0, -0.2, 0])
    assert np.all(J[:, 3:] == 0) and np.linalg.norm(J[:, :3]) > 0   # joelho/tornozelo não movem o fêmur


# ---------- velocidades e acelerações ----------
def test_velocity_and_acceleration_vs_finite_differences_of_trajectory():
    ch = build_spatial_lower_limb()
    q0, qd0, qdd0 = limb_q(), RNG.uniform(-1, 1, 6), RNG.uniform(-2, 2, 6)
    qf = lambda t: q0 + qd0 * t + 0.5 * qdd0 * t * t
    p_local = [0.24, 0, 0]
    pos = lambda t: ch.point_world("foot", p_local, ch.forward_kinematics(qf(t)))
    h = 1e-4
    v_fd = (pos(h) - pos(-h)) / (2 * h)
    a_fd = (pos(h) - 2 * pos(0) + pos(-h)) / h ** 2
    v, w = K.velocity(ch, q0, qd0, "foot", p_local)
    a, alpha = K.acceleration(ch, q0, qd0 + 0 * qdd0, qdd0, "foot", p_local)
    assert np.allclose(v, v_fd, atol=1e-7) and np.allclose(a, a_fd, atol=2e-5)
    # ω: derivada da orientação; α: diferença da velocidade angular
    R = lambda t: ch.forward_kinematics(qf(t)).T["foot"][:3, :3]
    ax, ang = matrix_log(R(h) @ R(-h).T)
    assert np.allclose(ax * ang / (2 * h), w, atol=1e-6)
    wv = lambda t: K.velocity(ch, qf(t), qd0 + qdd0 * t, "foot", p_local)[1]
    assert np.allclose(alpha, (wv(h) - wv(-h)) / (2 * h), atol=1e-5)


def test_jdot_qd_zero_when_qd_zero_and_known_case():
    ch = planar_arm(1.0, 1.0)
    assert np.allclose(K.jdot_qd(ch, [0.3, 0.4], [0, 0], "l2", [1, 0, 0])[0], 0)
    # rotação pura de elo de 1 m a ω=2 rad/s: aceleração centrípeta ω²·r = 4 apontando para a origem
    one = SpatialChain("one", [body("base"), body("a", 1.0)], [revolute("j", "base", "a", [0, 0, 1], [0, 0, 0], (-3, 3))], "base")
    a, alpha = K.acceleration(one, [0.0], [2.0], [0.0], "a", [1, 0, 0])
    assert np.allclose(a, [-4, 0, 0], atol=1e-6) and np.allclose(alpha, 0, atol=1e-9)


# ---------- IK ----------
def test_ik_recovers_reachable_position_and_pose_targets():
    ch = build_spatial_lower_limb()
    p_local = [0.24, 0, 0]
    ok_pos = ok_pose = 0
    for _ in range(15):
        qt = limb_q()
        fk = ch.forward_kinematics(qt)
        target = T.apply(fk.T["foot"], p_local)
        r = solve_ik(ch, "foot", p_local, target, q0=np.zeros(6) + 0.05, max_iter=300)
        if r.converged:
            ok_pos += 1
            assert np.linalg.norm(ch.point_world("foot", p_local, ch.forward_kinematics(r.q)) - target) < 1e-6
            assert not ch.violations(r.q)
        r2 = solve_ik(ch, "foot", p_local, target, q0=qt + 0.1, target_R=fk.T["foot"][:3, :3], max_iter=300)
        if r2.converged:
            ok_pose += 1
            fk2 = ch.forward_kinematics(r2.q)
            assert np.linalg.norm(T.apply(fk2.T["foot"], p_local) - target) < 1e-5
            ax, ang = matrix_log(fk.T["foot"][:3, :3] @ fk2.T["foot"][:3, :3].T)
            assert ang < 1e-5
    assert ok_pos >= 13 and ok_pose >= 13   # alvos gerados por FK dentro dos limites: devem ser alcançáveis


def test_ik_unreachable_limit_iteration_and_singularity_messages():
    ch = planar_arm(0.5, 0.4)
    r = solve_ik(ch, "l2", [0.4, 0, 0], [2.0, 0, 0])
    assert not r.converged and "inalcançável" in r.message and r.iterations == 0
    assert np.isclose(reach_bound(ch, "l2", [0.4, 0, 0]), 0.9)
    # alvo na fronteira do alcance, partida em configuração singular (braço esticado): sem NaN, resposta definida
    r = solve_ik(ch, "l2", [0.4, 0, 0], [0.9 - 1e-9, 0.0, 0.0], q0=[0.0, 0.0], tol_pos=1e-6)
    assert np.all(np.isfinite(r.q)) and r.converged
    r = solve_ik(ch, "l2", [0.4, 0, 0], [0.3, 0.5, 0.0], q0=[0.0, 0.0], max_iter=1, damping=0.05, max_step=0.001)
    assert not r.converged and "Não convergiu" in r.message
    assert np.all(np.isfinite(solve_ik(ch, "l2", [0.4, 0, 0], [0.0, 0.0, 0.0], q0=[0.0, 0.0]).q))  # alvo no ponto da base


def test_ik_respects_joint_limits_and_reports_clamping():
    ch = SpatialChain("c", [body("base"), body("a", 0.5)], [revolute("j", "base", "a", [0, 0, 1], [0, 0, 0], (0.0, 0.3))], "base")
    r = solve_ik(ch, "a", [0.5, 0, 0], [0.0, 0.5, 0.0], q0=[0.0])    # exigiria 90°; limite 0,3 rad
    assert not r.converged and 0.0 <= r.q[0] <= 0.3 + 1e-12 and r.clamped


# ---------- trajetórias ----------
def test_joint_min_jerk_boundaries_and_cartesian_line_with_ik():
    t, q, qd, qdd = joint_min_jerk([0, 0], [1.0, -2.0], 2.0, 101)
    assert np.allclose(q[0], [0, 0]) and np.allclose(q[-1], [1, -2]) and np.allclose(qd[[0, -1]], 0, atol=1e-12) and np.allclose(qdd[[0, -1]], 0, atol=1e-9)
    with pytest.raises(TrajectoryError):
        joint_min_jerk([0], [1, 2], 1.0, 10)
    ch = planar_arm(0.5, 0.4)
    _, pos, vel, _ = cartesian_line([0.6, 0.2, 0.0], [0.4, 0.5, 0.0], 1.0, 11)
    qs, res = track_cartesian(ch, "l2", [0.4, 0, 0], pos, [0.5, 0.8])
    for qi, p in zip(qs, pos):
        assert np.linalg.norm(ch.point_world("l2", [0.4, 0, 0], ch.forward_kinematics(qi)) - p) < 1e-6
    with pytest.raises(TrajectoryError):
        track_cartesian(ch, "l2", [0.4, 0, 0], [[5.0, 0, 0]], [0.5, 0.8])

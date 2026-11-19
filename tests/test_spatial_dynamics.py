"""ETAPA 3 — dinâmica espacial e integração: soluções analíticas, pêndulos, correntes, M simétrica/PD, energia, equilíbrio."""
import math

import numpy as np
import pytest

from biomechanics.human_model.spatial_lower_limb import build_spatial_lower_limb
from biomechanics.spatial.rigid_body import RigidBody, cylinder_inertia
from biomechanics.spatial.spatial_chain import SpatialChain
from biomechanics.spatial.spatial_dynamics import DynamicsError, ExternalLoad, SpatialDynamics
from biomechanics.spatial.spatial_joints import prismatic, revolute, spherical
from simulation.kinematics.planar import TwoLink
from simulation.numerical_integrators.integrate import IntegrationCancelled, IntegrationError, simulate
from simulation.validation import checks as V

RNG = np.random.default_rng(11)
G = 9.80665


def link(bid, L=0.5, m=2.0, axis=0, com=0.5, r=0.03):
    d = [0.0, 0.0, 0.0]
    d[axis] = 1.0
    return RigidBody(bid, bid, L, m, [x * com * L for x in d], cylinder_inertia(m, L, r, 2 if axis != 2 else 0).tolist(),
                     {"shape": "cylinder", "radius_m": r, "p0": [0, 0, 0], "p1": [x * L for x in d]})


def base():
    return RigidBody("base", "base", 0.1, 1.0, [0, 0, 0], np.eye(3).tolist(), {"shape": "cylinder", "radius_m": 0.02, "p0": [0, 0, 0], "p1": [0.1, 0, 0]})


def pendulum(L=0.8, m=3.0, com=0.5, Izz_cm=None, axis=(0, 0, 1)):
    """Pêndulo físico plano: eixo z, elo ao longo de −y em q=0 (pendurado). q medido de −y rumo a +x."""
    Iz = m * L * L / 12 if Izz_cm is None else Izz_cm
    I = np.diag([Iz, 1e-4, Iz])   # haste fina ao longo de y (momentos válidos: Iz ≤ Iz + 1e-4)
    b = RigidBody("a", "a", L, m, [0, -com * L, 0], I.tolist(), {"shape": "cylinder", "radius_m": 0.02, "p0": [0, 0, 0], "p1": [0, -L, 0]})
    return SpatialChain("p", [base(), b], [revolute("j", "base", "a", list(axis), [0, 0, 0], (-3.1, 3.1))], "base")


def planar_double(l1=0.5, l2=0.4, m1=2.0, m2=1.5, c1=0.5, c2=0.5):
    def b(bid, L, m, c):
        Iz = m * L * L / 12
        I = np.diag([1e-4, Iz, Iz])   # haste fina ao longo de x
        return RigidBody(bid, bid, L, m, [c * L, 0, 0], I.tolist(), {"shape": "cylinder", "radius_m": 0.02, "p0": [0, 0, 0], "p1": [L, 0, 0]})
    return SpatialChain("dp", [base(), b("l1", l1, m1, c1), b("l2", l2, m2, c2)],
                        [revolute("j1", "base", "l1", [0, 0, 1], [0, 0, 0], (-3.1, 3.1)),
                         revolute("j2", "l1", "l2", [0, 0, 1], [l1, 0, 0], (-3.1, 3.1))], "base")


def analytic_planar_M_G(l1, l2, m1, m2, c1, c2, I1, I2, q):
    """Pêndulo duplo plano com ângulos relativos (q2 relativo a q1); y para cima, g=-y. Fórmulas clássicas (Spong)."""
    q1, q2 = q
    a = l1 * c1; b = l2 * c2
    d11 = m1 * a * a + m2 * (l1 * l1 + b * b + 2 * l1 * b * math.cos(q2)) + I1 + I2
    d12 = m2 * (b * b + l1 * b * math.cos(q2)) + I2
    d22 = m2 * b * b + I2
    g1 = (m1 * a + m2 * l1) * G * math.cos(q1) + m2 * b * G * math.cos(q1 + q2)
    g2 = m2 * b * G * math.cos(q1 + q2)
    return np.array([[d11, d12], [d12, d22]]), np.array([g1, g2])


# ---------- pêndulo físico ----------
def test_physical_pendulum_mass_gravity_and_small_oscillation_period():
    L, m, com = 0.8, 3.0, 0.5
    ch = pendulum(L, m, com)
    dyn = SpatialDynamics(ch)
    I_pivot = m * L * L / 12 + m * (com * L) ** 2
    assert np.isclose(dyn.mass_matrix([0.3])[0, 0], I_pivot, rtol=1e-12)
    assert np.isclose(dyn.gravity_vector([0.3])[0], m * G * com * L * math.sin(0.3), rtol=1e-9)   # ∂V/∂q = m g d sen q
    assert np.isclose(dyn.coriolis_vector([0.3], [2.0])[0], 0.0, atol=1e-8)
    T_small = 2 * math.pi * math.sqrt(I_pivot / (m * G * com * L))
    q0 = 0.02
    tr = simulate(dyn, [q0], [0.0], 2 * T_small, 0.001)
    # cruzamentos por zero: período = 2 × intervalo entre cruzamentos consecutivos
    idx = np.where(np.diff(np.sign(tr.q[:, 0])) != 0)[0]
    tc = [tr.t[i] - tr.q[i, 0] * (tr.t[i + 1] - tr.t[i]) / (tr.q[i + 1, 0] - tr.q[i, 0]) for i in idx]
    assert abs(2 * (tc[1] - tc[0]) - T_small) / T_small < 1e-4     # só aproxima por linearização (erro de amplitude ~q0²/16)


def test_pendulum_equilibrium_and_torque_to_hold():
    ch = pendulum()
    dyn = SpatialDynamics(ch)
    assert np.allclose(dyn.forward_dynamics([0.0], [0.0], [0.0]), 0.0, atol=1e-12)           # pendurado: equilíbrio estável
    q = [0.7]
    tau_hold = dyn.inverse_dynamics(q, [0.0], [0.0])
    assert np.allclose(dyn.forward_dynamics(q, [0.0], tau_hold), 0.0, atol=1e-9)             # torque estático segura a pose
    assert np.isclose(tau_hold[0], 3.0 * G * 0.4 * math.sin(0.7), rtol=1e-8)


def test_pendulum_released_horizontally_initial_acceleration_analytic():
    L, m, com = 0.8, 3.0, 0.5
    dyn = SpatialDynamics(pendulum(L, m, com))
    I_p = m * L * L / 12 + m * (com * L) ** 2
    qdd = dyn.forward_dynamics([math.pi / 2], [0.0], [0.0])
    assert np.isclose(qdd[0], -m * G * com * L / I_p, rtol=1e-9)     # horizontal: α = −m g d / I_pivô


# ---------- cadeia plana: comparação com fórmulas e com o módulo planar existente ----------
def test_double_pendulum_M_and_G_match_analytic_formulas():
    l1, l2, m1, m2, c1, c2 = 0.5, 0.4, 2.0, 1.5, 0.5, 0.4
    ch = planar_double(l1, l2, m1, m2, c1, c2)
    dyn = SpatialDynamics(ch)
    for _ in range(10):
        q = RNG.uniform(-2.5, 2.5, 2)
        Ma, Ga = analytic_planar_M_G(l1, l2, m1, m2, c1, c2, m1 * l1 * l1 / 12, m2 * l2 * l2 / 12, q)
        assert np.allclose(dyn.mass_matrix(q), Ma, atol=1e-10)
        assert np.allclose(dyn.gravity_vector(q), Ga, atol=1e-9)


def test_chain_planar_matches_existing_planar_chain_dynamics():
    """Regressão cruzada: o motor espacial reproduz a PlanarChain já validada (M, G, C q̇, dinâmica direta/inversa)."""
    from biomechanics.force_engine.chain_dynamics import PlanarChain
    from biomechanics.force_engine.planar_dynamics import Segment
    l1, l2, m1, m2, c1, c2 = 0.5, 0.4, 2.0, 1.5, 0.5, 0.4
    ref = PlanarChain([Segment(l1, m1, c1), Segment(l2, m2, c2)])
    dyn = SpatialDynamics(planar_double(l1, l2, m1, m2, c1, c2))
    for _ in range(15):
        q, qd, tau = RNG.uniform(-2.5, 2.5, 2), RNG.uniform(-3, 3, 2), RNG.uniform(-5, 5, 2)
        assert np.allclose(dyn.mass_matrix(q), ref.mass_matrix(q), atol=1e-6)      # Izz idêntico; Ixx/Iyy extras não afetam o plano
        assert np.allclose(dyn.gravity_vector(q), ref.gravity_torque(q), atol=1e-9)
        assert np.allclose(dyn.coriolis_vector(q, qd), ref.coriolis_vector(q, qd), atol=1e-6)
        assert np.allclose(dyn.forward_dynamics(q, qd, tau), ref.forward_dynamics(q, qd, tau), atol=1e-6)
        assert np.allclose(dyn.inverse_dynamics(q, qd, tau), ref.inverse_dynamics(q, qd, tau), atol=1e-6)


# ---------- propriedades de M e C ----------
def test_mass_matrix_symmetric_positive_definite_on_limb_random_poses():
    ch = build_spatial_lower_limb()
    dyn = SpatialDynamics(ch)
    lo, hi = ch.limits()
    for _ in range(25):
        q = RNG.uniform(lo, hi)
        r = V.mass_matrix_checks(dyn, q)
        assert r["symmetric"] and r["positive_definite"] and r["min_eig"] > 1e-9 and np.isfinite(r["cond"])


def test_passivity_Mdot_minus_2C_skew_symmetric():
    ch = build_spatial_lower_limb()
    dyn = SpatialDynamics(ch)
    lo, hi = ch.limits()
    for _ in range(6):
        q, qd = RNG.uniform(lo * 0.7, hi * 0.7), RNG.uniform(-2, 2, 6)
        assert V.passivity_check(dyn, q, qd) < 1e-5


def test_coriolis_newton_euler_equals_christoffel_method():
    ch = build_spatial_lower_limb()
    dyn = SpatialDynamics(ch)
    lo, hi = ch.limits()
    for _ in range(6):
        q, qd = RNG.uniform(lo * 0.8, hi * 0.8), RNG.uniform(-3, 3, 6)
        assert np.allclose(dyn.coriolis_vector(q, qd), dyn.coriolis_matrix(q, qd) @ qd, atol=1e-5)


def test_gravity_vector_is_gradient_of_potential_energy():
    ch = build_spatial_lower_limb()
    dyn = SpatialDynamics(ch)
    q = RNG.uniform(*[x * 0.5 for x in ch.limits()])
    h = 1e-6
    g_fd = np.array([(dyn.potential_energy(q + h * e) - dyn.potential_energy(q - h * e)) / (2 * h) for e in np.eye(6)])
    assert np.allclose(dyn.gravity_vector(q), g_fd, atol=1e-6)


def test_kinetic_energy_equals_sum_of_translational_and_rotational_parts():
    ch = planar_double()
    dyn = SpatialDynamics(ch)
    q, qd = [0.4, -0.7], [1.2, -0.5]
    from biomechanics.spatial.spatial_jacobian import point_jacobian
    fk = ch.forward_kinematics(q)
    K = 0.0
    for b in ("l1", "l2"):
        Jv, Jw = point_jacobian(ch, fk, b, ch.com_world(b, fk))
        v, w = Jv @ qd, Jw @ qd
        R = fk.T[b][:3, :3]
        K += 0.5 * ch.bodies[b].mass_kg * v @ v + 0.5 * w @ (R @ ch.bodies[b].inertia @ R.T) @ w
    assert np.isclose(dyn.kinetic_energy(q, qd), K, rtol=1e-12)


# ---------- dinâmica direta/inversa ----------
def test_inverse_forward_consistency_on_spatial_limb():
    ch = build_spatial_lower_limb()
    dyn = SpatialDynamics(ch)
    lo, hi = ch.limits()
    for _ in range(10):
        q, qd, qdd = RNG.uniform(lo, hi), RNG.uniform(-2, 2, 6), RNG.uniform(-5, 5, 6)
        assert V.inverse_forward_consistency(dyn, q, qd, qdd) < 1e-9


def test_external_force_equivalent_torque_and_static_equilibrium():
    ch = pendulum(0.8, 3.0, 0.5)
    q = [0.5]
    # força vertical F para cima na ponta equilibra o peso: τ_ext = Jᵀ F
    F_equiv = 3.0 * G * 0.4 * math.sin(0.5) / (0.8 * math.sin(0.5))      # braço de alavanca horizontal da ponta = L sen q
    dyn = SpatialDynamics(ch, loads=[ExternalLoad("a", (0.0, F_equiv, 0.0), (0.0, -0.8, 0.0))])
    assert np.allclose(dyn.forward_dynamics(q, [0.0], [0.0]), 0.0, atol=1e-9)
    assert np.allclose(dyn.inverse_dynamics(q, [0.0], [0.0]), 0.0, atol=1e-9)
    with pytest.raises(DynamicsError):
        SpatialDynamics(ch, loads=[ExternalLoad("zzz", (0, 1, 0))])
    pure = SpatialDynamics(ch, loads=[ExternalLoad("a", torque_nm=(0.0, 0.0, 2.5))])
    assert np.isclose(pure.external_generalized_force([0.1])[0], 2.5)


def test_prismatic_vertical_mass_free_fall_and_spring_free_equilibrium():
    b = RigidBody("a", "a", 0.1, 2.0, [0, 0, 0], np.eye(3).tolist(), {"shape": "cylinder", "radius_m": 0.02, "p0": [0, 0, 0], "p1": [0.1, 0, 0]})
    ch = SpatialChain("s", [base(), b], [prismatic("p", "base", "a", [0, 1, 0], [0, 0, 0], (-5, 5))], "base")
    dyn = SpatialDynamics(ch)
    assert np.isclose(dyn.mass_matrix([0.0])[0, 0], 2.0)
    assert np.isclose(dyn.forward_dynamics([0.0], [0.0], [0.0])[0], -G)       # queda livre: q̈ = −g
    tr = simulate(dyn, [0.0], [0.0], 0.5, 0.005)
    assert np.isclose(tr.q[-1, 0], -0.5 * G * 0.25, rtol=1e-9)                # x = ½ g t² (RK4 é exato para polinômio grau 2)
    assert np.isclose(tr.qd[-1, 0], -G * 0.5, rtol=1e-9)


# ---------- integração ----------
def test_energy_conservation_double_pendulum_rk4_and_adaptive():
    dyn = SpatialDynamics(planar_double())
    q0, qd0 = [1.0, 0.5], [0.0, 0.0]
    a = simulate(dyn, q0, qd0, 3.0, 0.001, method="rk4")
    b = simulate(dyn, q0, qd0, 3.0, 0.01, method="adaptive", rtol=1e-10, atol=1e-12)
    assert V.energy_drift(a)["relative"] < 1e-6
    assert V.energy_drift(b)["relative"] < 1e-6
    assert np.allclose(a.q[::10], b.q, atol=1e-5)                           # ambos os métodos concordam


def test_rk4_convergence_order_4_on_pendulum():
    dyn = SpatialDynamics(pendulum())
    ref = simulate(dyn, [1.0], [0.0], 1.0, 0.0005).q[-1, 0]
    errs = [abs(simulate(dyn, [1.0], [0.0], 1.0, h).q[-1, 0] - ref) for h in (0.02, 0.01)]
    rate = math.log2(errs[0] / errs[1])
    assert 3.5 < rate < 4.6, rate


def test_spatial_limb_energy_conservation_and_work_energy_with_torque():
    ch = build_spatial_lower_limb()
    dyn = SpatialDynamics(ch)
    q0 = np.radians([20, 5, 0, 30, 0, 0])
    qd0 = np.radians([10, 0, 5, -20, 0, 0])
    free = simulate(dyn, q0, qd0, 0.5, 0.0005)
    assert V.energy_drift(free)["relative"] < 1e-4
    tau_fn = lambda t, q, qd: np.array([5.0 * math.sin(4 * t), 0, 0, 3.0, 0, 0])
    forced = simulate(dyn, q0, qd0, 0.5, 0.0005, tau_fn=tau_fn)
    wb = V.work_energy_balance(forced)
    assert wb["residual_j"] < 5e-3 * max(1.0, abs(wb["delta_energy_j"]), abs(wb["work_j"]))


def test_deterministic_rerun_identical():
    dyn = SpatialDynamics(build_spatial_lower_limb())
    q0 = np.radians([15, 3, 2, 25, 5, 0])
    a = simulate(dyn, q0, np.zeros(6), 0.2, 0.001)
    b = simulate(dyn, q0, np.zeros(6), 0.2, 0.001)
    assert np.array_equal(a.q, b.q) and np.array_equal(a.me, b.me)


def test_cancel_progress_divergence_and_invalid_inputs():
    dyn = SpatialDynamics(planar_double())
    calls = []
    simulate(dyn, [0.5, 0.2], [0, 0], 0.1, 0.01, progress=calls.append)
    assert calls[0] == 0.0 and calls[-1] == 1.0 and all(0 <= c <= 1 for c in calls) and calls == sorted(calls)
    n = {"k": 0}
    def cancel():
        n["k"] += 1
        return n["k"] > 5
    with pytest.raises(IntegrationCancelled):
        simulate(dyn, [0.5, 0.2], [0, 0], 1.0, 0.001, cancelled=cancel)
    with pytest.raises(IntegrationError, match="Divergência"):
        simulate(dyn, [0.5, 0.2], [0, 0], 1.0, 0.01, tau_fn=lambda t, q, qd: np.array([1e9, 1e9]), max_speed_rad_s=1e3)
    for bad in (dict(duration_s=0), dict(dt_s=0), dict(dt_s=5.0), dict(method="x")):
        kw = dict(dyn=dyn, q0=[0, 0], qd0=[0, 0], duration_s=1.0, dt_s=0.01)
        kw.update(bad)
        with pytest.raises(IntegrationError):
            simulate(**kw)
    with pytest.raises(IntegrationError):
        simulate(dyn, [0.0], [0, 0], 1.0, 0.01)
    with pytest.raises(DynamicsError):
        dyn.forward_dynamics([0, np.nan], [0, 0], [0, 0])


def test_spherical_joint_pendulum_matches_planar_one_in_plane_and_conserves_energy_in_3d():
    m, L = 2.0, 0.6
    I = np.diag([m * L * L / 12, 1e-4, m * L * L / 12])
    b = RigidBody("a", "a", L, m, [0, -L / 2, 0], I.tolist(), {"shape": "cylinder", "radius_m": 0.02, "p0": [0, 0, 0], "p1": [0, -L, 0]})
    ch = SpatialChain("sph", [base(), b], [spherical("s", "base", "a", [0, 0, 0], limits_rad=[(-3.0, 3.0)] * 3)], "base")
    dyn = SpatialDynamics(ch)
    tr = simulate(dyn, [0.8, 0.3, 0.0], [0.0, 0.0, 0.0], 1.5, 0.0005)
    assert V.energy_drift(tr)["relative"] < 1e-6
    I_p = m * L * L / 12 + m * (L / 2) ** 2
    qdd = dyn.forward_dynamics([math.pi / 2, 0.0, 0.0], [0, 0, 0], [0, 0, 0])
    assert np.isclose(qdd[0], -m * G * (L / 2) / I_p, rtol=1e-8)

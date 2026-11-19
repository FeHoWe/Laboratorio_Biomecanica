import math

import numpy as np
import pytest

from biomechanics.force_engine.planar_dynamics import G, PlanarArm, Segment, center_of_mass, moment
from core.geometry import transforms as T
from core.units import UnitError, convert, deg2rad
from simulation.kinematics.planar import KinematicsError, TwoLink, finite_diff, min_jerk


# ---- unidades ----
def test_unit_conversions():
    assert convert(180, "deg", "rad") == pytest.approx(math.pi)
    assert convert(250, "mm", "m") == pytest.approx(0.25)
    assert convert(1.5, "kg", "g") == pytest.approx(1500)
    assert convert(10, "N.cm", "N.m") == pytest.approx(0.1)
    assert deg2rad(90) == pytest.approx(math.pi / 2)


def test_unit_dimension_check():
    with pytest.raises(UnitError):
        convert(1, "kg", "m")
    with pytest.raises(UnitError):
        convert(1, "furlong", "m")


# ---- geometria ----
def test_rotation_properties():
    R = T.rot_z(0.7) @ T.rot_x(-0.3) @ T.rot_y(1.1)
    assert T.is_rotation(R)
    assert np.allclose(T.rot_z(math.pi / 2) @ [1, 0, 0], [0, 1, 0], atol=1e-12)


def test_homogeneous_inverse_and_apply():
    Tm = T.homogeneous(T.rot_z(0.5), (1, 2, 3))
    assert np.allclose(Tm @ T.invert(Tm), np.eye(4), atol=1e-12)
    p = np.array([0.3, -0.2, 0.9])
    assert np.allclose(T.apply(T.invert(Tm), T.apply(Tm, p)), p)
    assert np.allclose(T.apply(T.homogeneous(T.rot_z(math.pi / 2), (1, 0, 0)), [1, 0, 0]), [1, 1, 0], atol=1e-12)


# ---- cinemática ----
def test_forward_known_poses():
    c = TwoLink(1.0, 1.0)
    assert np.allclose(c.forward(0, 0)["tip"], [2, 0])
    assert np.allclose(c.forward(math.pi / 2, 0)["tip"], [0, 2], atol=1e-12)
    assert np.allclose(c.forward(0, math.pi / 2)["tip"], [1, 1], atol=1e-12)


@pytest.mark.parametrize("elbow", ["up", "down"])
def test_inverse_roundtrip(elbow):
    c = TwoLink(0.45, 0.38)
    rng = np.random.default_rng(0)
    for _ in range(50):
        r = rng.uniform(abs(c.l1 - c.l2) + 1e-3, c.l1 + c.l2 - 1e-3)
        a = rng.uniform(-math.pi, math.pi)
        x, y = r * math.cos(a), r * math.sin(a)
        q1, q2 = c.inverse(x, y, elbow)
        assert np.allclose(c.forward(q1, q2)["tip"], [x, y], atol=1e-9)
        assert (q2 >= 0) == (elbow == "down")


def test_inverse_unreachable():
    c = TwoLink(1, 1)
    with pytest.raises(KinematicsError):
        c.inverse(3, 0)
    with pytest.raises(KinematicsError):
        TwoLink(1, 0)


def test_jacobian_matches_numeric():
    c = TwoLink(0.5, 0.4)
    q = np.array([0.4, 0.9])
    h = 1e-6
    Jn = np.zeros((2, 2))
    for i in range(2):
        d = np.zeros(2)
        d[i] = h
        Jn[:, i] = (c.forward(*(q + d))["tip"] - c.forward(*(q - d))["tip"]) / (2 * h)
    assert np.allclose(c.jacobian(*q), Jn, atol=1e-8)


def test_min_jerk_boundaries_and_derivatives():
    t, q, qd, qdd = min_jerk(0.0, 1.2, 2.0, 2001)
    assert q[0] == 0 and q[-1] == pytest.approx(1.2)
    assert qd[0] == 0 and qd[-1] == pytest.approx(0, abs=1e-12)
    assert qdd[0] == 0 and qdd[-1] == pytest.approx(0, abs=1e-12)
    assert np.allclose(finite_diff(t, q), qd, atol=1e-4)
    assert np.allclose(finite_diff(t, qd), qdd, atol=1e-3)
    assert qd.max() == pytest.approx(1.875 * 1.2 / 2.0, rel=1e-3)  # pico analítico 15/8 * d/T


# ---- estática ----
def test_moment_and_com():
    assert moment([2, 0], [0, 5]) == pytest.approx(10.0)
    assert moment([0, 3], [4, 0]) == pytest.approx(-12.0)
    assert np.allclose(center_of_mass([1, 3], [[0, 0], [4, 0]]), [3, 0])


def test_horizontal_arm_gravity_torque_analytic():
    arm = PlanarArm(Segment(1.0, 1.0), Segment(1.0, 1.0))
    t = arm.gravity_torque(0.0, 0.0)
    assert t[0] == pytest.approx(G * (0.5 + 1.5))
    assert t[1] == pytest.approx(G * 0.5)
    assert np.allclose(arm.gravity_torque(math.pi / 2, 0.0), 0, atol=1e-12)  # braço vertical


def test_static_torque_with_tip_force():
    arm = PlanarArm(Segment(1.0, 1.0), Segment(1.0, 1.0))
    # ambiente empurra a ponta para cima com 10 N em braço horizontal esticado (x=2)
    t = arm.static_torque(0.0, 0.0, (0.0, 10.0))
    assert t[0] == pytest.approx(G * 2.0 - 10 * 2.0)
    assert t[1] == pytest.approx(G * 0.5 - 10 * 1.0)


def test_gravity_torque_is_potential_gradient():
    arm = PlanarArm(Segment(0.45, 7.0, 0.43), Segment(0.40, 3.0, 0.4))
    q = np.array([0.3, 0.8])
    h = 1e-6

    def U(q):
        c1, c2 = arm.com_positions(*q)
        return G * (arm.s1.mass * c1[1] + arm.s2.mass * c2[1])

    grad = np.array([(U(q + [h, 0]) - U(q - [h, 0])) / (2 * h), (U(q + [0, h]) - U(q - [0, h])) / (2 * h)])
    assert np.allclose(arm.gravity_torque(*q), grad, atol=1e-6)


# ---- dinâmica ----
def test_inverse_forward_consistency():
    arm = PlanarArm(Segment(0.45, 7.0, 0.43), Segment(0.40, 3.0, 0.4))
    q, qd, qdd = np.array([0.2, 0.7]), np.array([0.5, -0.3]), np.array([1.0, 2.0])
    tau = arm.inverse_dynamics(q, qd, qdd)
    assert np.allclose(arm.forward_dynamics(q, qd, tau), qdd, atol=1e-10)


def test_energy_conservation_passive_swing():
    arm = PlanarArm(Segment(0.45, 7.0, 0.43), Segment(0.40, 3.0, 0.4))
    T_, X = arm.simulate([0.5, 0.3], [0.0, 0.0], t_end=2.0, dt=1e-3)
    E = np.array([arm.energy(x[:2], x[2:]) for x in X])
    assert np.max(np.abs(E - E[0])) < 1e-6 * max(1.0, abs(E[0])) + 1e-6


def test_pendulum_limit_period():
    """Segmento 2 desprezível: pêndulo físico de barra -> T = 2π sqrt(I_o/(m g a))."""
    L, m = 1.0, 2.0
    arm = PlanarArm(Segment(L, m), Segment(1e-3, 1e-9, inertia=1e-18))
    th0 = 0.05  # pequena amplitude
    # q1 absoluto medido do eixo x; equilíbrio em -pi/2
    q_eq = -math.pi / 2
    T_, X = arm.simulate([q_eq + th0, 0.0], [0.0, 0.0], t_end=4.0, dt=1e-3)
    th = X[:, 0] - q_eq
    idx = np.where((th[:-1] > 0) & (th[1:] <= 0))[0]  # cruzamentos descendentes
    period = T_[idx[1]] - T_[idx[0]]
    expected = 2 * math.pi * math.sqrt((m * L**2 / 3) / (m * G * L / 2))
    assert period == pytest.approx(expected, rel=2e-3)


def test_invalid_segment():
    from biomechanics.force_engine.planar_dynamics import DynamicsError
    with pytest.raises(DynamicsError):
        Segment(0, 1)

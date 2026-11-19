import math

import numpy as np
import pytest

from biomechanics.force_engine.chain_dynamics import PlanarChain
from biomechanics.force_engine.planar_dynamics import G, PlanarArm, Segment

SEGS2 = [Segment(0.45, 7.0, 0.43), Segment(0.40, 3.0, 0.4)]
SEGS3 = [Segment(0.43, 7.0, 0.43), Segment(0.40, 3.2, 0.43), Segment(0.24, 1.0, 0.45)]


def test_two_link_matches_planar_arm_everywhere():
    chain, arm = PlanarChain(SEGS2), PlanarArm(*SEGS2)
    rng = np.random.default_rng(3)
    for _ in range(25):
        q, qd, qdd = rng.uniform(-2, 2, 2), rng.uniform(-3, 3, 2), rng.uniform(-5, 5, 2)
        assert np.allclose(chain.mass_matrix(q), arm.mass_matrix(q[1]), atol=1e-12)
        assert np.allclose(chain.gravity_torque(q), arm.gravity_torque(*q), atol=1e-10)
        assert np.allclose(chain.coriolis_vector(q, qd), arm.coriolis_vector(q[1], *qd), atol=1e-6)
        assert np.allclose(chain.inverse_dynamics(q, qd, qdd, (3.0, -20.0)),
                           arm.inverse_dynamics(q, qd, qdd) - arm.chain.jacobian(*q).T @ [3.0, -20.0], atol=1e-6)
        assert chain.energy(q, qd) == pytest.approx(arm.energy(q, qd), rel=1e-12, abs=1e-12)


def test_mass_matrix_symmetric_positive_definite_n3():
    c = PlanarChain(SEGS3)
    rng = np.random.default_rng(4)
    for _ in range(20):
        M = c.mass_matrix(rng.uniform(-3, 3, 3))
        assert np.allclose(M, M.T, atol=1e-12) and np.all(np.linalg.eigvalsh(M) > 0)


def test_gravity_is_potential_gradient_n3():
    c = PlanarChain(SEGS3)
    q = np.array([0.3, -0.5, 0.9])
    U = lambda q: c.g * float(np.sum(c.m * c.com_points(q)[:, 1]))
    h = 1e-6
    grad = np.array([(U(q + h * e) - U(q - h * e)) / (2 * h) for e in np.eye(3)])
    assert np.allclose(c.gravity_torque(q), grad, atol=1e-6)


def test_horizontal_chain_static_torque_analytic_n3():
    segs = [Segment(1.0, 1.0, 0.5), Segment(1.0, 1.0, 0.5), Segment(1.0, 1.0, 0.5)]
    t = PlanarChain(segs).gravity_torque([0, 0, 0])
    assert np.allclose(t, [G * (0.5 + 1.5 + 2.5), G * (0.5 + 1.5), G * 0.5])


def test_tip_jacobian_matches_numeric_n3():
    c = PlanarChain(SEGS3)
    q, h = np.array([0.2, 0.7, -0.4]), 1e-6
    Jn = np.column_stack([(c.points(q + h * e)[-1] - c.points(q - h * e)[-1]) / (2 * h) for e in np.eye(3)])
    assert np.allclose(c.tip_jacobian(q), Jn, atol=1e-8)


def test_inverse_forward_consistency_n3():
    c = PlanarChain(SEGS3)
    q, qd, qdd = np.array([0.2, 0.7, -0.4]), np.array([0.5, -0.3, 0.8]), np.array([1.0, 2.0, -1.5])
    tau = c.inverse_dynamics(q, qd, qdd)
    assert np.allclose(c.forward_dynamics(q, qd, tau), qdd, atol=1e-8)


def test_energy_conservation_n3_passive():
    c = PlanarChain(SEGS3)
    T, X = c.simulate([0.2, 0.5, -0.3], [0.0, 0.0, 0.0], 1.5, 1e-3)
    E = np.array([c.energy(x[:3], x[3:]) for x in X])
    assert np.max(np.abs(E - E[0])) < 1e-4 * max(1.0, abs(E[0]))

"""Estática e dinâmica de cadeia planar de 2 segmentos (Lagrange).

Hipóteses: segmentos rígidos e homogêneos descritos por massa, posição do CM (fração
do comprimento a partir da junta proximal) e momento de inércia em torno do CM (kg.m²);
sem atrito articular, sem músculos; movimento no plano vertical (gravidade em -y).
Unidades SI. Torque de junta = torque que o atuador/músculo precisa aplicar.
Convenção de q como em simulation.kinematics.planar (q1 absoluto, q2 relativo).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core.exceptions import NexusError, SimulationCancelled
from simulation.kinematics.planar import TwoLink

G = 9.80665  # m/s², gravidade padrão


class DynamicsError(NexusError):
    pass


@dataclass(frozen=True)
class Segment:
    length: float          # m
    mass: float            # kg
    com_frac: float = 0.5  # CM como fração do comprimento (proximal -> distal)
    inertia: float | None = None  # kg.m² em torno do CM; None -> barra fina: m L²/12

    def __post_init__(self) -> None:
        if not (self.length > 0 and self.mass > 0 and 0 <= self.com_frac <= 1):
            raise DynamicsError("Segmento inválido: length>0, mass>0, 0<=com_frac<=1")

    @property
    def I(self) -> float:
        return self.inertia if self.inertia is not None else self.mass * self.length**2 / 12.0


def moment(r, F) -> float:
    """Momento escalar (z) de força F aplicada em r (2D): r x F  [N.m]."""
    r, F = np.asarray(r, float), np.asarray(F, float)
    return float(r[0] * F[1] - r[1] * F[0])


def center_of_mass(masses, positions) -> np.ndarray:
    m = np.asarray(masses, float)
    if m.sum() <= 0:
        raise DynamicsError("Massa total deve ser positiva")
    return (m[:, None] * np.asarray(positions, float)).sum(axis=0) / m.sum()


class PlanarArm:
    def __init__(self, s1: Segment, s2: Segment, g: float = G) -> None:
        self.s1, self.s2, self.g = s1, s2, g
        self.chain = TwoLink(s1.length, s2.length)

    # ---- geometria dos CMs ----
    def com_positions(self, q1: float, q2: float) -> tuple[np.ndarray, np.ndarray]:
        j = self.chain.forward(q1, q2)["joint"]
        c1 = self.s1.com_frac * self.s1.length * np.array([np.cos(q1), np.sin(q1)])
        c2 = j + self.s2.com_frac * self.s2.length * np.array([np.cos(q1 + q2), np.sin(q1 + q2)])
        return c1, c2

    def total_com(self, q1: float, q2: float) -> np.ndarray:
        c1, c2 = self.com_positions(q1, q2)
        return center_of_mass([self.s1.mass, self.s2.mass], [c1, c2])

    # ---- estática ----
    def gravity_torque(self, q1: float, q2: float) -> np.ndarray:
        """Torques de junta [N.m] para sustentar o peso dos segmentos (equilíbrio estático)."""
        s1, s2, g = self.s1, self.s2, self.g
        a1, a2 = s1.com_frac * s1.length, s2.com_frac * s2.length
        c1, c12 = np.cos(q1), np.cos(q1 + q2)
        t2 = s2.mass * g * a2 * c12
        t1 = s1.mass * g * a1 * c1 + s2.mass * g * (s1.length * c1 + a2 * c12)
        return np.array([t1, t2])

    def static_torque(self, q1: float, q2: float, tip_force=(0.0, 0.0)) -> np.ndarray:
        """Torque de junta para equilíbrio com força externa F [N] aplicada pelo ambiente na ponta.

        tau = tau_gravidade - J^T F.
        """
        J = self.chain.jacobian(q1, q2)
        return self.gravity_torque(q1, q2) - J.T @ np.asarray(tip_force, float)

    # ---- dinâmica (Lagrange) ----
    def mass_matrix(self, q2: float) -> np.ndarray:
        s1, s2 = self.s1, self.s2
        l1, a1, a2 = s1.length, s1.com_frac * s1.length, s2.com_frac * s2.length
        m1, m2 = s1.mass, s2.mass
        c2 = np.cos(q2)
        # q1 absoluto, q2 relativo
        M22 = m2 * a2**2 + s2.I
        M12 = M22 + m2 * l1 * a2 * c2
        M11 = m1 * a1**2 + s1.I + m2 * (l1**2 + a2**2 + 2 * l1 * a2 * c2) + s2.I
        return np.array([[M11, M12], [M12, M22]])

    def coriolis_vector(self, q2: float, qd1: float, qd2: float) -> np.ndarray:
        s1, s2 = self.s1, self.s2
        h = -s2.mass * s1.length * s2.com_frac * s2.length * np.sin(q2)
        return np.array([h * (2 * qd1 * qd2 + qd2**2), -h * qd1**2])

    def inverse_dynamics(self, q, qd, qdd) -> np.ndarray:
        q1, q2 = q
        M = self.mass_matrix(q2)
        return M @ np.asarray(qdd, float) + self.coriolis_vector(q2, *qd) + self.gravity_torque(q1, q2)

    def forward_dynamics(self, q, qd, tau) -> np.ndarray:
        q1, q2 = q
        M = self.mass_matrix(q2)
        rhs = np.asarray(tau, float) - self.coriolis_vector(q2, *qd) - self.gravity_torque(q1, q2)
        return np.linalg.solve(M, rhs)

    def energy(self, q, qd) -> float:
        """Energia mecânica total [J] (referência de potencial: y = 0)."""
        M = self.mass_matrix(q[1])
        qd = np.asarray(qd, float)
        T = 0.5 * qd @ M @ qd
        c1, c2 = self.com_positions(*q)
        U = self.g * (self.s1.mass * c1[1] + self.s2.mass * c2[1])
        return float(T + U)

    def simulate(self, q0, qd0, t_end: float, dt: float = 1e-3, tau_fn=None, progress=None, should_cancel=None):
        """Integra com RK4 (passo fixo). tau_fn(t, q, qd) -> torques [N.m]; None -> passivo."""
        if t_end <= 0 or dt <= 0:
            raise DynamicsError("t_end e dt devem ser > 0")
        n = int(round(t_end / dt))
        tau_fn = tau_fn or (lambda t, q, qd: np.zeros(2))

        def f(t, x):
            q, qd = x[:2], x[2:]
            return np.concatenate([qd, self.forward_dynamics(q, qd, tau_fn(t, q, qd))])

        x = np.concatenate([q0, qd0]).astype(float)
        T, X = np.empty(n + 1), np.empty((n + 1, 4))
        T[0], X[0] = 0.0, x
        for i in range(n):
            if i % 200 == 0:
                if should_cancel is not None and should_cancel():
                    raise SimulationCancelled("Simulação cancelada")
                if progress is not None:
                    progress(int(100 * i / n))
            t = T[i]
            k1 = f(t, x)
            k2 = f(t + dt / 2, x + dt / 2 * k1)
            k3 = f(t + dt / 2, x + dt / 2 * k2)
            k4 = f(t + dt, x + dt * k3)
            x = x + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
            T[i + 1], X[i + 1] = T[i] + dt, x
        if not np.all(np.isfinite(X)):
            raise DynamicsError("Integração divergiu (valores não finitos)")
        return T, X

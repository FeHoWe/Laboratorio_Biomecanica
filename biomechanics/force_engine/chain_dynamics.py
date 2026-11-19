"""Dinâmica de cadeia planar de N segmentos (Lagrange), ângulos de junta RELATIVOS.

q[0] = ângulo do segmento 1 em relação ao eixo x (absoluto); q[k] (k>=1) = ângulo do segmento k+1
relativo ao anterior. Hipóteses: corpos rígidos, juntas rotativas ideais, sem atrito/músculos, plano
vertical (gravidade em -y), SI. M = Σ m_i JvᵀJv + I_i JwᵀJw; G = ∂U/∂q; C q̇ por derivada de M.
Para N = 2 coincide com PlanarArm (verificado em testes).
"""
from __future__ import annotations

import numpy as np

from biomechanics.force_engine.planar_dynamics import DynamicsError, G, Segment
from core.exceptions import SimulationCancelled


class PlanarChain:
    def __init__(self, segments: list[Segment], g: float = G) -> None:
        if len(segments) < 1:
            raise DynamicsError("A cadeia precisa de ao menos 1 segmento")
        self.segs, self.g, self.n = list(segments), g, len(segments)
        self.L = np.array([s.length for s in segments])
        self.m = np.array([s.mass for s in segments])
        self.a = np.array([s.com_frac * s.length for s in segments])
        self.I = np.array([s.I for s in segments])

    # ---- cinemática ----
    def theta(self, q) -> np.ndarray:
        return np.cumsum(np.asarray(q, float))

    def points(self, q) -> np.ndarray:
        """(N+1, 2): origem, junta 1, ..., ponta."""
        th = self.theta(q)
        d = np.column_stack([np.cos(th), np.sin(th)]) * self.L[:, None]
        return np.vstack([[0.0, 0.0], np.cumsum(d, axis=0)])

    def com_points(self, q) -> np.ndarray:
        th = self.theta(q)
        pts = self.points(q)
        return pts[:-1] + np.column_stack([np.cos(th), np.sin(th)]) * self.a[:, None]

    def tip_jacobian(self, q) -> np.ndarray:
        pts = self.points(q)
        tip = pts[-1]
        J = np.zeros((2, self.n))
        for k in range(self.n):
            r = tip - pts[k]
            J[:, k] = (-r[1], r[0])
        return J

    def _com_jacobians(self, q):
        pts, com = self.points(q), self.com_points(q)
        Jv = np.zeros((self.n, 2, self.n))
        for i in range(self.n):
            for k in range(i + 1):
                r = com[i] - pts[k]
                Jv[i, :, k] = (-r[1], r[0])
        return Jv

    # ---- dinâmica ----
    def mass_matrix(self, q) -> np.ndarray:
        Jv = self._com_jacobians(q)
        M = np.zeros((self.n, self.n))
        for i in range(self.n):
            Jw = np.zeros(self.n)
            Jw[: i + 1] = 1.0
            M += self.m[i] * Jv[i].T @ Jv[i] + self.I[i] * np.outer(Jw, Jw)
        return M

    def gravity_torque(self, q) -> np.ndarray:
        Jv = self._com_jacobians(q)
        return sum(self.m[i] * self.g * Jv[i][1, :] for i in range(self.n))

    def coriolis_vector(self, q, qd, h: float = 1e-6) -> np.ndarray:
        q, qd = np.asarray(q, float), np.asarray(qd, float)
        dM = np.zeros((self.n, self.n, self.n))  # dM[k] = ∂M/∂q_k
        for k in range(self.n):
            e = np.zeros(self.n)
            e[k] = h
            dM[k] = (self.mass_matrix(q + e) - self.mass_matrix(q - e)) / (2 * h)
        Mdot = sum(dM[k] * qd[k] for k in range(self.n))
        dT_dq = np.array([0.5 * qd @ dM[k] @ qd for k in range(self.n)])
        return Mdot @ qd - dT_dq

    def inverse_dynamics(self, q, qd, qdd, tip_force=(0.0, 0.0)) -> np.ndarray:
        tau = (self.mass_matrix(q) @ np.asarray(qdd, float) + self.coriolis_vector(q, qd) + self.gravity_torque(q))
        F = np.asarray(tip_force, float)
        if F.any():
            tau = tau - self.tip_jacobian(q).T @ F
        return tau

    def forward_dynamics(self, q, qd, tau) -> np.ndarray:
        rhs = np.asarray(tau, float) - self.coriolis_vector(q, qd) - self.gravity_torque(q)
        return np.linalg.solve(self.mass_matrix(q), rhs)

    def energy(self, q, qd) -> float:
        qd = np.asarray(qd, float)
        T = 0.5 * qd @ self.mass_matrix(q) @ qd
        U = self.g * float(np.sum(self.m * self.com_points(q)[:, 1]))
        return float(T + U)

    def simulate(self, q0, qd0, t_end, dt=1e-3, tau_fn=None, progress=None, should_cancel=None):
        if t_end <= 0 or dt <= 0:
            raise DynamicsError("t_end e dt devem ser > 0")
        n_steps = int(round(t_end / dt))
        tau_fn = tau_fn or (lambda t, q, qd: np.zeros(self.n))
        n = self.n

        def f(t, x):
            q, qd = x[:n], x[n:]
            return np.concatenate([qd, self.forward_dynamics(q, qd, tau_fn(t, q, qd))])

        x = np.concatenate([q0, qd0]).astype(float)
        T, X = np.empty(n_steps + 1), np.empty((n_steps + 1, 2 * n))
        T[0], X[0] = 0.0, x
        for i in range(n_steps):
            if i % 100 == 0:
                if should_cancel is not None and should_cancel():
                    raise SimulationCancelled("Simulação cancelada")
                if progress is not None:
                    progress(int(100 * i / n_steps))
            t = T[i]
            k1 = f(t, x)
            k2 = f(t + dt / 2, x + dt / 2 * k1)
            k3 = f(t + dt / 2, x + dt / 2 * k2)
            k4 = f(t + dt, x + dt * k3)
            x = x + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
            T[i + 1], X[i + 1] = T[i] + dt, x
        if not np.all(np.isfinite(X)):
            raise DynamicsError("Integração divergiu")
        return T, X

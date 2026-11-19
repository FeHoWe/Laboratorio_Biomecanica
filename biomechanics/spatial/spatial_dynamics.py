"""Dinâmica espacial:  M(q) q̈ + C(q,q̇) q̇ + G(q) = τ + Σ J_pᵀ F_p     (SI: kg, m, s, rad, N, N·m).

M(q) = Σ_b [ m_b Jv_bᵀ Jv_b + Jw_bᵀ I_b^mundo Jw_b ],  I_b^mundo = R_b I_cm R_bᵀ   (I_cm = inércia em torno do CM, eixos do corpo)
G(q) = ∂V/∂q = −Σ m_b gᵀ Jv_b            (V = −Σ m_b g·r_cm,b; g = vetor gravidade, ex.: (0,−9.80665,0))
C(q,q̇) q̇ pelos símbolos de Christoffel: Γ_ijk = ½(∂M_ij/∂q_k + ∂M_ik/∂q_j − ∂M_jk/∂q_i), com ∂M/∂q por diferenças centrais
(h = 1e-6, erro O(h²)); C_ij = Σ_k Γ_ijk q̇_k. Propriedade verificada em teste: Ṁ − 2C antissimétrica ⇒ conservação de energia.
Forças externas: aplicadas em um ponto local de um corpo (vetor força no mundo, N); torque externo puro em um corpo (N·m, mundo).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from biomechanics.spatial import transforms as T
from biomechanics.spatial.spatial_chain import SpatialChain
from biomechanics.spatial.spatial_jacobian import point_jacobian
from core.exceptions import NexusError

G_STD = 9.80665


class DynamicsError(NexusError):
    pass


@dataclass
class ExternalLoad:
    """Força (N) em ponto local de um corpo e/ou torque puro (N·m), vetores no referencial do mundo."""
    body: str
    force_n: tuple = (0.0, 0.0, 0.0)
    point_local_m: tuple = (0.0, 0.0, 0.0)
    torque_nm: tuple = (0.0, 0.0, 0.0)


@dataclass
class SpatialDynamics:
    chain: SpatialChain
    gravity: tuple = (0.0, -G_STD, 0.0)
    loads: list = field(default_factory=list)
    h_fd: float = 1e-6

    def __post_init__(self) -> None:
        g = np.asarray(self.gravity, float)
        if g.shape != (3,) or not np.all(np.isfinite(g)):
            raise DynamicsError("gravity deve ser um vetor (3,) finito [m/s²]")
        self.g = g
        for L in self.loads:
            if L.body not in self.chain.bodies:
                raise DynamicsError(f"Carga externa em corpo desconhecido: {L.body}")

    # ---- matriz de massa ----
    def mass_matrix(self, q) -> np.ndarray:
        ch = self.chain
        fk = ch.forward_kinematics(q)
        n = ch.n_dof
        M = np.zeros((n, n))
        for bid in ch.moving_bodies():
            b = ch.bodies[bid]
            Jv, Jw = point_jacobian(ch, fk, bid, ch.com_world(bid, fk))
            R = fk.T[bid][:3, :3]
            Iw = R @ b.inertia @ R.T
            M += b.mass_kg * Jv.T @ Jv + Jw.T @ Iw @ Jw
        return 0.5 * (M + M.T)

    def gravity_vector(self, q) -> np.ndarray:
        ch = self.chain
        fk = ch.forward_kinematics(q)
        Gq = np.zeros(ch.n_dof)
        for bid in ch.moving_bodies():
            Jv, _ = point_jacobian(ch, fk, bid, ch.com_world(bid, fk))
            Gq -= ch.bodies[bid].mass_kg * (Jv.T @ self.g)
        return Gq

    def mass_derivatives(self, q) -> np.ndarray:
        """dM[k] = ∂M/∂q_k  (n,n,n) por diferenças centrais."""
        q = np.asarray(q, float)
        n, h = self.chain.n_dof, self.h_fd
        dM = np.zeros((n, n, n))
        for k in range(n):
            qp, qm = q.copy(), q.copy()
            qp[k] += h
            qm[k] -= h
            dM[k] = (self.mass_matrix(qp) - self.mass_matrix(qm)) / (2 * h)
        return dM

    def coriolis_matrix(self, q, qd) -> np.ndarray:
        dM = self.mass_derivatives(q)            # dM[k,i,j] = ∂M_ij/∂q_k
        qd = np.asarray(qd, float)
        n = self.chain.n_dof
        C = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                C[i, j] = 0.5 * sum((dM[k, i, j] + dM[j, i, k] - dM[i, j, k]) * qd[k] for k in range(n))
        return C

    def coriolis_vector(self, q, qd) -> np.ndarray:
        """C(q,q̇) q̇ (n,) por Newton-Euler: Σ_b [ m Jvᵀ(J̇v q̇) + Jwᵀ(I_w J̇w q̇ + ω × I_w ω) ].
        J̇ q̇ por diferença central ao longo de q̇ (erro O(h²)); equivale ao método de Christoffel (verificado em teste)
        com custo ~O(n) em vez de O(n²) avaliações da matriz de massa."""
        ch = self.chain
        q, qd = np.asarray(q, float), np.asarray(qd, float)
        s = float(np.max(np.abs(qd)))
        if s < 1e-14:
            return np.zeros(ch.n_dof)
        step = self.h_fd / s
        fk0, fkp, fkm = ch.forward_kinematics(q), ch.forward_kinematics(q + step * qd), ch.forward_kinematics(q - step * qd)
        out = np.zeros(ch.n_dof)
        for bid in ch.moving_bodies():
            b = ch.bodies[bid]
            Jv, Jw = point_jacobian(ch, fk0, bid, ch.com_world(bid, fk0))
            Jvp, Jwp = point_jacobian(ch, fkp, bid, ch.com_world(bid, fkp))
            Jvm, Jwm = point_jacobian(ch, fkm, bid, ch.com_world(bid, fkm))
            a_b = (Jvp - Jvm) @ qd / (2 * step)
            al_b = (Jwp - Jwm) @ qd / (2 * step)
            R = fk0.T[bid][:3, :3]
            Iw = R @ b.inertia @ R.T
            w = Jw @ qd
            out += Jv.T @ (b.mass_kg * a_b) + Jw.T @ (Iw @ al_b + np.cross(w, Iw @ w))
        return out

    # ---- cargas externas ----
    def external_generalized_force(self, q, loads=None) -> np.ndarray:
        loads = self.loads if loads is None else loads
        ch = self.chain
        tau = np.zeros(ch.n_dof)
        if not loads:
            return tau
        fk = ch.forward_kinematics(q)
        for L in loads:
            p = T.apply(fk.T[L.body], L.point_local_m)
            Jv, Jw = point_jacobian(ch, fk, L.body, p)
            tau += Jv.T @ np.asarray(L.force_n, float) + Jw.T @ np.asarray(L.torque_nm, float)
        return tau

    # ---- energias, potência, trabalho ----
    def kinetic_energy(self, q, qd) -> float:
        qd = np.asarray(qd, float)
        return float(0.5 * qd @ self.mass_matrix(q) @ qd)

    def potential_energy(self, q) -> float:
        ch = self.chain
        fk = ch.forward_kinematics(q)
        return float(-sum(ch.bodies[b].mass_kg * (self.g @ ch.com_world(b, fk)) for b in ch.moving_bodies()))

    def mechanical_energy(self, q, qd) -> float:
        return self.kinetic_energy(q, qd) + self.potential_energy(q)

    @staticmethod
    def joint_power(tau, qd) -> np.ndarray:
        """P_k = τ_k q̇_k [W] por DOF."""
        return np.asarray(tau, float) * np.asarray(qd, float)

    @staticmethod
    def work(t, power) -> float:
        """∫P dt [J] (trapézios)."""
        t, p = np.asarray(t, float), np.asarray(power, float)
        return float(np.sum(0.5 * (p[1:] + p[:-1]) * np.diff(t))) if len(t) > 1 else 0.0

    # ---- dinâmica inversa e direta ----
    def inverse_dynamics(self, q, qd, qdd, with_loads: bool = True) -> np.ndarray:
        """τ = M q̈ + C q̇ + G − τ_ext   (torque articular necessário para produzir q̈)."""
        q, qd, qdd = (np.asarray(x, float) for x in (q, qd, qdd))
        self._check(q, qd, qdd)
        tau = self.mass_matrix(q) @ qdd + self.coriolis_vector(q, qd) + self.gravity_vector(q)
        if with_loads:
            tau = tau - self.external_generalized_force(q)
        return tau

    def forward_dynamics(self, q, qd, tau, with_loads: bool = True) -> np.ndarray:
        """q̈ = M⁻¹(τ + τ_ext − C q̇ − G)."""
        q, qd, tau = (np.asarray(x, float) for x in (q, qd, tau))
        self._check(q, qd, tau)
        rhs = tau - self.coriolis_vector(q, qd) - self.gravity_vector(q)
        if with_loads:
            rhs = rhs + self.external_generalized_force(q)
        M = self.mass_matrix(q)
        try:
            return np.linalg.solve(M, rhs)
        except np.linalg.LinAlgError as exc:
            raise DynamicsError("Matriz de massa singular") from exc

    def _check(self, *vs) -> None:
        for v in vs:
            if v.shape != (self.chain.n_dof,) or not np.all(np.isfinite(v)):
                raise DynamicsError(f"Vetor deve ter {self.chain.n_dof} valores finitos")

    def state_derivative(self, tau_fn=None):
        """f(t, x) com x = [q, q̇], para integradores. tau_fn(t, q, qd) → τ (padrão: 0)."""
        n = self.chain.n_dof

        def f(t, x):
            q, qd = x[:n], x[n:]
            tau = np.zeros(n) if tau_fn is None else np.asarray(tau_fn(t, q, qd), float)
            return np.concatenate([qd, self.forward_dynamics(q, qd, tau)])
        return f

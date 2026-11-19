"""Integração temporal com cancelamento, progresso, detecção de divergência e registro completo.

Estado x = [q, q̇]; registra t, q, q̇, q̈ (da função de dinâmica), τ aplicado, energias (E_c, E_p, E_m) e potência articular.
Método "rk4" (passo fixo, ordem 4) ou "adaptive" (scipy solve_ivp DOP853/RK45 com rtol/atol; amostrado em passos de saída fixos).
Divergência: valores não finitos, |q̇| > limite, ou deriva de energia > limite (somente se não há torque/cargas, opcional).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from core.exceptions import NexusError, SimulationCancelled
from simulation.spatial_dynamics.dynamics import SpatialDynamics


class IntegrationError(NexusError):
    pass


class IntegrationCancelled(SimulationCancelled):
    pass


@dataclass
class Trajectory:
    t: np.ndarray
    q: np.ndarray
    qd: np.ndarray
    qdd: np.ndarray
    tau: np.ndarray
    ke: np.ndarray
    pe: np.ndarray
    me: np.ndarray
    power: np.ndarray            # (n_t, n_dof)
    method: str = "rk4"
    dt: float = 0.0
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in self.__dict__.items()}


def _rk4_step(f, t, x, dt):
    k1 = f(t, x)
    k2 = f(t + dt / 2, x + dt / 2 * k1)
    k3 = f(t + dt / 2, x + dt / 2 * k2)
    k4 = f(t + dt, x + dt * k3)
    return x + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)


def simulate(dyn: SpatialDynamics, q0, qd0, duration_s: float, dt_s: float = 0.002, tau_fn: Callable | None = None,
             method: str = "rk4", rtol: float = 1e-9, atol: float = 1e-11, max_speed_rad_s: float = 1e4,
             progress: Callable[[float], None] | None = None, cancelled: Callable[[], bool] | None = None,
             stop_on_limit_violation: bool = False) -> Trajectory:
    ch = dyn.chain
    n = ch.n_dof
    q0, qd0 = np.asarray(q0, float), np.asarray(qd0, float)
    if q0.shape != (n,) or qd0.shape != (n,) or not (np.all(np.isfinite(q0)) and np.all(np.isfinite(qd0))):
        raise IntegrationError(f"q0 e qd0 devem ter {n} valores finitos")
    if not (duration_s > 0 and dt_s > 0):
        raise IntegrationError("duração e passo devem ser positivos")
    if dt_s > duration_s:
        raise IntegrationError("passo maior que a duração")
    if method not in ("rk4", "adaptive"):
        raise IntegrationError("método deve ser 'rk4' ou 'adaptive'")
    steps = int(round(duration_s / dt_s))
    t = np.arange(steps + 1) * dt_s
    f = dyn.state_derivative(tau_fn)
    X = np.zeros((steps + 1, 2 * n))
    X[0] = np.concatenate([q0, qd0])

    def check(i):
        if cancelled and cancelled():
            raise IntegrationCancelled("Simulação cancelada pelo usuário")
        x = X[i]
        if not np.all(np.isfinite(x)) or np.max(np.abs(x[n:])) > max_speed_rad_s:
            raise IntegrationError(f"Divergência numérica em t = {t[i]:.6g} s (valores não finitos ou |q̇| > {max_speed_rad_s:g} rad/s); "
                                   "reduza o passo ou revise os parâmetros")
        if progress and (i % max(1, steps // 100) == 0 or i == steps):
            progress(i / steps)

    if progress:
        progress(0.0)
    if method == "rk4":
        for i in range(steps):
            X[i + 1] = _rk4_step(f, t[i], X[i], dt_s)
            check(i + 1)
    else:
        from scipy.integrate import solve_ivp
        state = {"last": -1}

        def rhs(tt, x):
            if cancelled and cancelled():
                raise IntegrationCancelled("Simulação cancelada pelo usuário")
            if progress:
                progress(min(0.999, tt / duration_s))
            return f(tt, x)
        sol = solve_ivp(rhs, (0.0, t[-1]), X[0], method="DOP853", t_eval=t, rtol=rtol, atol=atol)
        if not sol.success or sol.y.shape[1] != len(t):
            raise IntegrationError(f"Integrador adaptativo falhou: {sol.message}")
        X = sol.y.T.copy()
        for i in range(len(t)):
            check(i)
    Q, QD = X[:, :n], X[:, n:]
    QDD, TAU = np.zeros((len(t), n)), np.zeros((len(t), n))
    KE, PE = np.zeros(len(t)), np.zeros(len(t))
    for i in range(len(t)):
        tau = np.zeros(n) if tau_fn is None else np.asarray(tau_fn(t[i], Q[i], QD[i]), float)
        TAU[i] = tau
        QDD[i] = dyn.forward_dynamics(Q[i], QD[i], tau)
        KE[i], PE[i] = dyn.kinetic_energy(Q[i], QD[i]), dyn.potential_energy(Q[i])
    viol = [(float(t[i]), ch.violations(Q[i])) for i in range(len(t)) if ch.violations(Q[i])]
    if viol and stop_on_limit_violation:
        raise IntegrationError(f"Limite articular violado em t = {viol[0][0]:.4g} s: {viol[0][1][0]}")
    if progress:
        progress(1.0)
    return Trajectory(t, Q, QD, QDD, TAU, KE, PE, KE + PE, TAU * QD, method, dt_s,
                      {"limit_violations": len(viol), "first_violation": viol[0] if viol else None})

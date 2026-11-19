"""Atuador de junta com curva torque-velocidade linear (modelo tipo motor DC no eixo da junta).

τ_max(ω) = τ_stall · max(0, 1 − |ω| / ω_sem_carga). Eficiência η: potência elétrica = potência mecânica
positiva / η (sem regeneração). Parâmetros DEMONSTRATIVOS (não correspondem a produto real).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from core.exceptions import NexusError


class ActuatorError(NexusError):
    pass


@dataclass
class Actuator:
    tau_stall_nm: float = 40.0        # torque de bloqueio na junta
    omega_noload_rad_s: float = 8.0   # velocidade angular sem carga
    efficiency: float = 0.7           # 0 < η <= 1
    mass_kg: float = 1.5              # informativo (a massa estrutural entra em added_masses_kg)

    def validate(self) -> None:
        if not (self.tau_stall_nm > 0 and self.omega_noload_rad_s > 0 and self.mass_kg >= 0):
            raise ActuatorError("tau_stall_nm e omega_noload_rad_s devem ser > 0; mass_kg >= 0")
        if not 0 < self.efficiency <= 1:
            raise ActuatorError("efficiency deve estar em (0, 1]")

    def tau_limit(self, omega: float) -> float:
        return self.tau_stall_nm * max(0.0, 1.0 - abs(omega) / self.omega_noload_rad_s)

    def saturate(self, tau_cmd: float, omega: float) -> tuple[float, bool]:
        lim = self.tau_limit(omega)
        out = max(-lim, min(lim, tau_cmd))
        return out, abs(tau_cmd) > lim + 1e-12

    def electrical_power(self, tau: float, omega: float) -> float:
        p = tau * omega
        return max(p, 0.0) / self.efficiency

    def to_dict(self) -> dict:
        return asdict(self)

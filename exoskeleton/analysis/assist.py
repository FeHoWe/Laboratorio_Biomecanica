"""EXO-001 — Análise de assistência articular por exoesqueleto.

Calcula, ao longo de uma trajetória de mínimo jerk, o torque articular requerido (dinâmica inversa),
com e sem exoesqueleto (massa adicionada nos segmentos), e o torque que resta ao humano após a assistência.
Modos: 'proportional' (fração do torque requerido) e 'gravity' (fração do torque de gravidade).
Hipóteses: exoesqueleto rígido e alinhado à junta (sem folga/atrito/deslizamento), massa adicional concentrada no
CM do segmento (CM inalterado), atuador ideal exceto pela curva torque-velocidade e eficiência; sem
reação do solo; sem músculos. Parâmetros DEMONSTRATIVOS.
"""
from __future__ import annotations

import csv
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from biomechanics.force_engine.chain_dynamics import PlanarChain
from biomechanics.force_engine.planar_dynamics import Segment
from core.exceptions import NexusError
from exoskeleton.actuators.actuator import Actuator
from research.experiments.bio001 import HYPOTHESES, SOURCE_DEMO, _trapz
from research.experiments.bio002 import ChainModel, default_params as _bio2_default
from simulation.kinematics.planar import min_jerk

EXPERIMENT_ID = "EXO-001"
MODES = ("proportional", "gravity")


class ExoError(NexusError):
    pass


@dataclass
class ExoConfig:
    joint_index: int = 1                      # 0-based: 1 = joelho no modelo humano
    mode: str = "proportional"
    gain: float = 0.5                         # fração (0..1+) do torque requerido / de gravidade
    added_masses_kg: list = field(default_factory=lambda: [0.0, 1.2, 0.3])
    actuator: Actuator = field(default_factory=Actuator)


@dataclass
class Exo001Params:
    model: ChainModel
    exo: ExoConfig
    duration_s: float = 1.0
    samples: int = 201

    def validate(self) -> None:
        self.model.validate()
        n = len(self.model.lengths_m)
        e = self.exo
        if e.mode not in MODES:
            raise ExoError(f"mode deve ser um de {MODES}")
        if not 0 <= e.joint_index < n:
            raise ExoError(f"joint_index deve estar em [0, {n - 1}]")
        if not (math.isfinite(e.gain) and e.gain >= 0):
            raise ExoError("gain deve ser >= 0")
        if len(e.added_masses_kg) != n or any(m < 0 for m in e.added_masses_kg):
            raise ExoError(f"added_masses_kg deve ter {n} valores >= 0")
        e.actuator.validate()
        if not self.duration_s > 0 or not (isinstance(self.samples, int) and 5 <= self.samples <= 5001):
            raise ExoError("duration_s > 0 e samples inteiro em [5, 5001]")

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Exo001Params":
        m = dict(d["model"])
        m["tip_force_n"] = tuple(m.get("tip_force_n", (0.0, 0.0)))
        e = dict(d["exo"])
        e["actuator"] = Actuator(**e["actuator"])
        return Exo001Params(ChainModel(**m), ExoConfig(**e), float(d["duration_s"]), int(d["samples"]))


def default_params() -> Exo001Params:
    return Exo001Params(_bio2_default().model_a, ExoConfig())


def run(p: Exo001Params) -> dict:
    p.validate()
    cfg, e = p.model, p.exo
    j, n, T = e.joint_index, len(cfg.lengths_m), p.samples
    base = cfg.chain()
    loaded = PlanarChain([Segment(l, m + dm, c) for l, m, c, dm in
                          zip(cfg.lengths_m, cfg.masses_kg, cfg.com_fracs, e.added_masses_kg)])
    r = math.radians
    tr = [min_jerk(r(s), r(en), p.duration_s, T) for s, en in zip(cfg.q_start_deg, cfg.q_end_deg)]
    t = tr[0][0]
    q = np.column_stack([x[1] for x in tr])
    qd = np.column_stack([x[2] for x in tr])
    qdd = np.column_stack([x[3] for x in tr])
    tau0, tauL = np.zeros((T, n)), np.zeros((T, n))
    exo, human, lim = np.zeros(T), np.zeros((T, n)), np.zeros(T)
    sat = np.zeros(T, bool)
    elec = np.zeros(T)
    points = np.zeros((T, n + 1, 2))
    for i in range(T):
        tau0[i] = base.inverse_dynamics(q[i], qd[i], qdd[i], cfg.tip_force_n)
        tauL[i] = loaded.inverse_dynamics(q[i], qd[i], qdd[i], cfg.tip_force_n)
        ref = tauL[i, j] if e.mode == "proportional" else loaded.gravity_torque(q[i])[j]
        cmd = e.gain * ref
        w = qd[i, j]
        exo[i], sat[i] = e.actuator.saturate(cmd, w)
        lim[i] = e.actuator.tau_limit(w)
        human[i] = tauL[i]
        human[i, j] = tauL[i, j] - exo[i]
        elec[i] = e.actuator.electrical_power(exo[i], w)
        points[i] = loaded.points(q[i])
    pk = lambda a: float(np.max(np.abs(a)))
    rms = lambda a: float(np.sqrt(np.mean(np.square(a))))
    base_pk, load_pk, hum_pk = pk(tau0[:, j]), pk(tauL[:, j]), pk(human[:, j])
    summary = {
        "joint_index": j, "mode": e.mode, "gain": e.gain,
        "baseline_peak_torque_nm": base_pk, "loaded_peak_torque_nm": load_pk, "human_peak_torque_nm": hum_pk,
        "baseline_rms_torque_nm": rms(tau0[:, j]), "loaded_rms_torque_nm": rms(tauL[:, j]), "human_rms_torque_nm": rms(human[:, j]),
        "human_peak_reduction_vs_baseline_pct": 100.0 * (1 - hum_pk / base_pk) if base_pk > 0 else 0.0,
        "actuator_peak_torque_nm": pk(exo), "actuator_peak_mech_power_w": pk(exo * qd[:, j]),
        "actuator_electrical_energy_j": _trapz(elec, t), "saturation_fraction": float(sat.mean()),
        "added_mass_total_kg": float(sum(e.added_masses_kg)), "total_length_m": float(sum(cfg.lengths_m)),
    }
    msgs = []
    if sat.any():
        msgs.append(f"AVISO: atuador saturou em {100 * sat.mean():.1f}% das amostras (torque limitado pela curva torque-velocidade).")
    if e.gain > 1:
        msgs.append("AVISO: ganho > 1 (assistência acima de 100% do torque de referência).")
    if summary["loaded_peak_torque_nm"] > summary["baseline_peak_torque_nm"]:
        msgs.append("Nota: a massa do exoesqueleto aumenta o torque requerido da junta (efeito incluído no cálculo).")
    msgs.append("Parâmetros demonstrativos: resultados ilustram o método, sem validade para dispositivos reais.")
    A = {"name": "Humano + exoesqueleto (DEMONSTRATIVO)", "t": t, "q": q, "qd": qd, "points": points,
         "tip_xy": points[:, -1, :], "joint_xy": points[:, 1, :], "joint_names": cfg.joint_names,
         "tau_baseline": tau0, "tau_loaded": tauL, "tau_exo": exo, "tau_human": human, "tau_limit": lim,
         "saturated": sat, "elec_power": elec, "summary": summary}
    return {"id": EXPERIMENT_ID, "params": p.to_dict(), "A": A, "messages": msgs}


def summary_dict(res: dict) -> dict:
    return {"A": res["A"]["summary"], "messages": res["messages"]}


def export_csv(res: dict, path: Path | str) -> None:
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    a = res["A"]
    j = a["summary"]["joint_index"]
    try:
        with open(tmp, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["t_s", "q_deg", "qd_deg_s", "tau_baseline_Nm", "tau_loaded_Nm", "tau_exo_Nm", "tau_human_Nm",
                        "tau_limit_Nm", "saturated", "elec_power_W"])
            for i, ti in enumerate(a["t"]):
                w.writerow([f"{ti:.6f}", f"{math.degrees(a['q'][i, j]):.9g}", f"{math.degrees(a['qd'][i, j]):.9g}",
                            f"{a['tau_baseline'][i, j]:.9g}", f"{a['tau_loaded'][i, j]:.9g}", f"{a['tau_exo'][i]:.9g}",
                            f"{a['tau_human'][i, j]:.9g}", f"{a['tau_limit'][i]:.9g}", int(a["saturated"][i]),
                            f"{a['elec_power'][i]:.9g}"])
        tmp.replace(path)
    except OSError as exc:
        raise ExoError(f"Falha ao exportar CSV: {exc}") from exc


def report_markdown(res: dict) -> str:
    p = Exo001Params.from_dict(res["params"])
    s = res["A"]["summary"]
    jn = p.model.joint_names[p.exo.joint_index]
    ac = p.exo.actuator
    L = [f"# Relatório técnico — {EXPERIMENT_ID} Assistência articular por exoesqueleto", "",
         "> Plataforma de pesquisa/aprendizado computacional. Não é dispositivo médico nem projeto de dispositivo real.", "",
         "## 1. Parâmetros de entrada (SI)", "", f"Modelo: {p.model.name} ({p.model.source})",
         f"Junta assistida: {p.exo.joint_index + 1} ({jn}); modo: {p.exo.mode}; ganho: {p.exo.gain}",
         f"Massas adicionadas por segmento (kg): {p.exo.added_masses_kg}",
         f"Atuador: τ_bloqueio={ac.tau_stall_nm} N·m, ω_sem_carga={ac.omega_noload_rad_s} rad/s, η={ac.efficiency}",
         f"Duração: {p.duration_s} s; amostras: {p.samples}.", "", "## 2. Hipóteses", ""] + [f"- {h}" for h in HYPOTHESES[:5]] + [
         "- Exoesqueleto rígido e alinhado à junta; massa adicional concentrada no CM do segmento.",
         "- Atuador com curva torque-velocidade linear e eficiência constante; sem regeneração.", "",
         "## 3. Método", "", "Dinâmica inversa de Lagrange sem e com massa do exoesqueleto; τ_exo = saturação(ganho·referência; curva τ-ω); "
         "τ_humano = τ_requerido(com exo) − τ_exo; energia elétrica = ∫ P_mec⁺/η dt.", "", "## 4. Resultados", "",
         "| Grandeza | Valor |", "|---|---|",
         f"| Torque de pico sem exo (N·m) | {s['baseline_peak_torque_nm']:.4g} |",
         f"| Torque de pico com exo, sem assistência (N·m) | {s['loaded_peak_torque_nm']:.4g} |",
         f"| Torque de pico humano com assistência (N·m) | {s['human_peak_torque_nm']:.4g} |",
         f"| Redução do pico vs. sem exo (%) | {s['human_peak_reduction_vs_baseline_pct']:.4g} |",
         f"| RMS humano (N·m) | {s['human_rms_torque_nm']:.4g} |",
         f"| Torque de pico do atuador (N·m) | {s['actuator_peak_torque_nm']:.4g} |",
         f"| Potência mecânica de pico do atuador (W) | {s['actuator_peak_mech_power_w']:.4g} |",
         f"| Energia elétrica (J) | {s['actuator_electrical_energy_j']:.4g} |",
         f"| Fração de amostras saturadas | {s['saturation_fraction']:.3g} |", "",
         "## 5. Mensagens de validação", ""] + [f"- {m}" for m in res["messages"]] + [
         "", "## 6. Limitações", "", "- Modelo 2D, sem músculos, atrito, folgas, contato com solo ou controle em malha fechada.",
         "- Parâmetros do atuador e do exoesqueleto demonstrativos; não representam produto real.", "- Sem validação experimental.", ""]
    return "\n".join(L)

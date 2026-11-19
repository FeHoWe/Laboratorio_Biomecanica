"""BIO-003 — Spatial lower limb dynamics (dinâmica espacial do membro inferior, 6 DOFs).

Cadeia pelve (fixa) → fêmur (quadril 3 DOF) → tíbia (joelho 1 DOF) [+ fíbula fixa] → pé (tornozelo 2 DOFs), dinâmica espacial
M(q)q̈ + C(q,q̇)q̇ + G(q) = τ + Jᵀ F, integrada por RK4 (passo fixo) ou DOP853 (adaptativo). Torque articular imposto por DOF:
τ_k(t) = τ_const_k + τ_amp_k · sen(2π f_k t). Parâmetros DEMONSTRATIVOS; simplificações mecânicas; sem músculos/contato/atrito.
Ângulos em graus nas entradas; saídas internas em rad (SI).
"""
from __future__ import annotations

import csv
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from biomechanics.human_model.lower_limb import LowerLimbModel, SegmentDef
from biomechanics.human_model.spatial_lower_limb import DOF_NAMES, EXTRA_LIMITS_DEG, build_spatial_lower_limb
from biomechanics.spatial.spatial_chain import SpatialChain
from biomechanics.spatial.spatial_dynamics import G_STD, SpatialDynamics
from core.exceptions import NexusError
from research.experiments.bio001 import HYPOTHESES, SOURCE_DEMO
from simulation.numerical_integrators.integrate import simulate
from simulation.validation import checks as V

EXPERIMENT_ID = "BIO-003"
SEGMENTS = ("femur", "tibia", "foot")
MAX_STEPS = 200_000


class Bio003Error(NexusError):
    pass


def _default_limits() -> list:
    m = LowerLimbModel()
    return [[m.joints["hip"].min_deg, m.joints["hip"].max_deg], list(EXTRA_LIMITS_DEG["hip_abd"]), list(EXTRA_LIMITS_DEG["hip_rot"]),
            [m.joints["knee"].min_deg, m.joints["knee"].max_deg], [m.joints["ankle"].min_deg, m.joints["ankle"].max_deg],
            list(EXTRA_LIMITS_DEG["ankle_inv"])]


@dataclass
class Bio003Params:
    segments: dict = field(default_factory=lambda: {k: {"length_m": v.length_m, "mass_kg": v.mass_kg, "com_frac": v.com_frac}
                                                    for k, v in LowerLimbModel().segments.items() if k in SEGMENTS})
    limits_deg: list = field(default_factory=_default_limits)
    q0_deg: list = field(default_factory=lambda: [20.0, 5.0, 0.0, 30.0, 0.0, 0.0])
    qd0_deg_s: list = field(default_factory=lambda: [0.0] * 6)
    gravity_m_s2: tuple = (0.0, -G_STD, 0.0)
    tau_const_nm: list = field(default_factory=lambda: [0.0] * 6)
    tau_amp_nm: list = field(default_factory=lambda: [0.0] * 6)
    tau_freq_hz: list = field(default_factory=lambda: [1.0] * 6)
    duration_s: float = 1.0
    dt_s: float = 0.002
    method: str = "rk4"
    source: str = SOURCE_DEMO

    def validate(self) -> None:
        for name in SEGMENTS:
            s = self.segments.get(name)
            if not s or not (s["length_m"] > 0 and s["mass_kg"] > 0 and 0 <= s["com_frac"] <= 1):
                raise Bio003Error(f"Segmento inválido ou ausente: {name} (comprimento>0, massa>0, 0≤CM≤1)")
        for key in ("q0_deg", "qd0_deg_s", "tau_const_nm", "tau_amp_nm", "tau_freq_hz"):
            v = getattr(self, key)
            if len(v) != 6 or not all(math.isfinite(x) for x in v):
                raise Bio003Error(f"'{key}' deve ter 6 valores finitos")
        if len(self.limits_deg) != 6 or any(len(l) != 2 or not l[0] < l[1] for l in self.limits_deg):
            raise Bio003Error("limits_deg: 6 pares [mín, máx] com mín < máx")
        for k, (q, (lo, hi)) in enumerate(zip(self.q0_deg, self.limits_deg)):
            if not (lo - 1e-9 <= q <= hi + 1e-9):
                raise Bio003Error(f"Pose inicial: {DOF_NAMES[k]} = {q}° fora dos limites [{lo}, {hi}]°")
        if any(f < 0 for f in self.tau_freq_hz):
            raise Bio003Error("frequências devem ser ≥ 0")
        g = np.asarray(self.gravity_m_s2, float)
        if g.shape != (3,) or not np.all(np.isfinite(g)):
            raise Bio003Error("gravidade deve ter 3 componentes finitas (m/s²)")
        if not (self.duration_s > 0 and self.dt_s > 0 and self.dt_s <= self.duration_s):
            raise Bio003Error("duração e passo devem ser > 0, com passo ≤ duração")
        if self.duration_s / self.dt_s > MAX_STEPS:
            raise Bio003Error(f"Passos demais ({self.duration_s / self.dt_s:.0f} > {MAX_STEPS}); aumente dt ou reduza a duração")
        if self.method not in ("rk4", "adaptive"):
            raise Bio003Error("método deve ser 'rk4' ou 'adaptive'")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["gravity_m_s2"] = list(self.gravity_m_s2)
        return d

    @staticmethod
    def from_dict(d: dict) -> "Bio003Params":
        d = dict(d)
        d["gravity_m_s2"] = tuple(d.get("gravity_m_s2", (0.0, -G_STD, 0.0)))
        try:
            return Bio003Params(**d)
        except TypeError as exc:
            raise Bio003Error(f"Parâmetros BIO-003 inválidos: {exc}") from exc


def default_params() -> Bio003Params:
    return Bio003Params()


def build_chain(p: Bio003Params) -> SpatialChain:
    m = LowerLimbModel()
    for name in SEGMENTS:
        s, o = m.segments[name], p.segments[name]
        m.segments[name] = SegmentDef(name, o["length_m"], o["mass_kg"], o["com_frac"], s.radius_m, s.source)
    lim = p.limits_deg
    m.joints["hip"].min_deg, m.joints["hip"].max_deg = lim[0]
    m.joints["knee"].min_deg, m.joints["knee"].max_deg = lim[3]
    m.joints["ankle"].min_deg, m.joints["ankle"].max_deg = lim[4]
    extra = {"hip_abd": tuple(lim[1]), "hip_rot": tuple(lim[2]), "ankle_inv": tuple(lim[5])}
    return build_spatial_lower_limb(m, extra)


def torque_function(p: Bio003Params):
    c, a, f = np.array(p.tau_const_nm, float), np.array(p.tau_amp_nm, float), np.array(p.tau_freq_hz, float)
    return lambda t, q, qd: c + a * np.sin(2 * math.pi * f * t)


def run(p: Bio003Params, progress=None, cancelled=None) -> dict:
    p.validate()
    ch = build_chain(p)
    dyn = SpatialDynamics(ch, gravity=p.gravity_m_s2)
    q0, qd0 = np.radians(p.q0_deg), np.radians(p.qd0_deg_s)
    chk0 = V.mass_matrix_checks(dyn, q0)
    tr = simulate(dyn, q0, qd0, p.duration_s, p.dt_s, torque_function(p), p.method, progress=(lambda x: progress(int(100 * x))) if progress else None,
                  cancelled=cancelled)
    n = len(tr.t)
    foot_len = ch.bodies["foot"].length_m
    from biomechanics.spatial import transforms as T
    tip, com = np.zeros((n, 3)), np.zeros((n, 3))
    for i in range(n):
        fk = ch.forward_kinematics(tr.q[i])
        tip[i] = T.apply(fk.T["foot"], [foot_len, 0, 0])
        com[i] = ch.total_com(tr.q[i])
    power_total = tr.power.sum(axis=1)
    work = V.work_energy_balance(tr)
    drift = V.energy_drift(tr)
    conservative = not (any(abs(x) > 0 for x in p.tau_const_nm) or any(abs(x) > 0 for x in p.tau_amp_nm))
    msgs = ["Parâmetros demonstrativos: resultados ilustram o método, não anatomia real nem precisão clínica.",
            "Simplificações mecânicas: quadril 3 DOF rotacionais, joelho 1 DOF, tornozelo 2 DOFs; sem músculos, ligamentos, contato ou atrito."]
    if not chk0["positive_definite"] or chk0["min_eig"] < 1e-8:
        msgs.append(f"AVISO: M(q0) quase singular (menor autovalor {chk0['min_eig']:.3g}).")
    if tr.meta["limit_violations"]:
        t0, v = tr.meta["first_violation"]
        msgs.append(f"AVISO: limite articular excedido em {tr.meta['limit_violations']} amostras (primeiro em t={t0:.4g} s: {v[0]}). "
                    "O motor NÃO impõe os limites na dinâmica; o resultado deve ser interpretado com cautela.")
    hip = next(j for j in ch.joints if j.jtype == "spherical")
    gm = np.array([hip.gimbal_margin(tr.q[i][ch.joint_slices[hip.name]]) for i in range(n)])
    if conservative and drift["relative"] > 1e-3:
        msgs.append(f"AVISO: deriva de energia relativa {drift['relative']:.2e} > 1e-3; reduza o passo.")
    if np.min(gm) < 0.05:
        msgs.append(f"AVISO: quadril próximo da singularidade de gimbal (margem mínima {np.min(gm):.3g}).")
    summary = {"samples": n, "method": p.method, "dt_s": p.dt_s, "conservative_run": conservative,
               "energy_initial_j": float(tr.me[0]), "energy_final_j": float(tr.me[-1]),
               "energy_drift_rel": drift["relative"], "work_torques_j": work["work_j"], "delta_energy_j": work["delta_energy_j"],
               "work_energy_residual_j": work["residual_j"],
               "peak_abs_ang_vel_rad_s": [float(np.max(np.abs(tr.qd[:, k]))) for k in range(6)],
               "peak_abs_ang_acc_rad_s2": [float(np.max(np.abs(tr.qdd[:, k]))) for k in range(6)],
               "peak_abs_torque_nm": [float(np.max(np.abs(tr.tau[:, k]))) for k in range(6)],
               "peak_abs_power_w": [float(np.max(np.abs(tr.power[:, k]))) for k in range(6)],
               "ke_max_j": float(tr.ke.max()), "pe_range_j": float(np.ptp(tr.pe)),
               "limit_violations": int(tr.meta["limit_violations"]), "mass_matrix_min_eig_q0": chk0["min_eig"],
               "mass_matrix_cond_q0": chk0["cond"], "foot_tip_final_m": [float(x) for x in tip[-1]]}
    return {"id": EXPERIMENT_ID, "params": p.to_dict(), "dof_names": list(DOF_NAMES), "t": tr.t, "q": tr.q, "qd": tr.qd, "qdd": tr.qdd,
            "tau": tr.tau, "ke": tr.ke, "pe": tr.pe, "me": tr.me, "power": tr.power, "power_total": power_total,
            "foot_tip": tip, "com": com, "summary": summary, "messages": msgs}


def summary_dict(res: dict) -> dict:
    return {"A": res["summary"], "messages": res["messages"]}


def export_csv(res: dict, path: Path | str) -> None:
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    names = res["dof_names"]
    head = ["t_s"] + [f"q_{n}_deg" for n in names] + [f"qd_{n}_deg_s" for n in names] + [f"qdd_{n}_deg_s2" for n in names] + \
           [f"tau_{n}_Nm" for n in names] + [f"power_{n}_W" for n in names] + ["KE_J", "PE_J", "ME_J", "foot_x_m", "foot_y_m", "foot_z_m",
                                                                              "com_x_m", "com_y_m", "com_z_m"]
    try:
        with open(tmp, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(head)
            for i, t in enumerate(res["t"]):
                row = [*np.degrees(res["q"][i]), *np.degrees(res["qd"][i]), *np.degrees(res["qdd"][i]), *res["tau"][i], *res["power"][i],
                       res["ke"][i], res["pe"][i], res["me"][i], *res["foot_tip"][i], *res["com"][i]]
                w.writerow([f"{t:.6f}", *(f"{v:.9g}" for v in row)])
        tmp.replace(path)
    except OSError as exc:
        raise Bio003Error(f"Falha ao exportar CSV: {exc}") from exc


def report_markdown(res: dict) -> str:
    p = Bio003Params.from_dict(res["params"])
    s = res["summary"]
    names = res["dof_names"]
    L = [f"# Relatório técnico — {EXPERIMENT_ID} Spatial lower limb dynamics", "",
         "> Plataforma de pesquisa/aprendizado computacional. Não é dispositivo médico. Sem precisão clínica.", "",
         "## 1. Parâmetros de entrada (SI)", "", f"Origem dos parâmetros: {p.source}", ""]
    for k, v in p.segments.items():
        L.append(f"- {k}: L={v['length_m']} m, m={v['mass_kg']} kg, CM={v['com_frac']}·L")
    L.append(f"- Gravidade: {tuple(p.gravity_m_s2)} m/s²")
    L += ["", "| DOF | limites (°) | q0 (°) | q̇0 (°/s) | τ const (N·m) | τ amp (N·m) | f (Hz) |", "|---|---|---|---|---|---|---|"]
    for k, n in enumerate(names):
        L.append(f"| {n} | [{p.limits_deg[k][0]}, {p.limits_deg[k][1]}] | {p.q0_deg[k]} | {p.qd0_deg_s[k]} | {p.tau_const_nm[k]} | {p.tau_amp_nm[k]} | {p.tau_freq_hz[k]} |")
    L += ["", f"Duração {p.duration_s} s, passo {p.dt_s} s, integrador: {p.method}.", "", "## 2. Hipóteses", ""] + [f"- {h}" for h in HYPOTHESES]
    L += ["- Quadril: 3 DOFs rotacionais (sequência Z-X-Y); joelho: 1 DOF; tornozelo: 2 DOFs (simplificações mecânicas).",
          "- Inércias de cilindros homogêneos (DEMONSTRATIVO). Limites articulares não são impostos na dinâmica (apenas reportados).",
          "", "## 3. Método", "", "M(q)q̈ + C(q,q̇)q̇ + G(q) = τ + JᵀF; integração RK4 / DOP853. Ver SPATIAL_ENGINE.md.", "",
          "## 4. Resultados", "",
          f"- Energia mecânica: inicial {s['energy_initial_j']:.6g} J, final {s['energy_final_j']:.6g} J"
          f" (deriva relativa {s['energy_drift_rel']:.3e}; {'sistema conservativo' if s['conservative_run'] else 'com torques: não se espera conservação'})",
          f"- Trabalho dos torques {s['work_torques_j']:.6g} J vs. variação de energia {s['delta_energy_j']:.6g} J (resíduo {s['work_energy_residual_j']:.3e} J)", ""]
    L += ["| DOF | pico |q̇| (rad/s) | pico |q̈| (rad/s²) | pico |τ| (N·m) | pico |P| (W) |", "|---|---|---|---|---|"]
    for k, n in enumerate(names):
        L.append(f"| {n} | {s['peak_abs_ang_vel_rad_s'][k]:.4g} | {s['peak_abs_ang_acc_rad_s2'][k]:.4g} | {s['peak_abs_torque_nm'][k]:.4g} | {s['peak_abs_power_w'][k]:.4g} |")
    L += ["", f"- Ponta do pé (final): {[round(x, 4) for x in s['foot_tip_final_m']]} m", "", "## 5. Mensagens de validação", ""] + [f"- {m}" for m in res["messages"]]
    L += ["", "## 6. Limitações", "", "- Sem músculos, ligamentos, contato com o solo, atrito ou limites articulares ativos.",
          "- Parâmetros demonstrativos; resultados não validados experimentalmente.", ""]
    return "\n".join(L)

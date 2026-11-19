"""SIM-001 — Dinâmica passiva de cadeia de 2 segmentos (pêndulo duplo com inércia de segmentos).

Integra M(q)q̈ + C + G = 0 (RK4, passo fixo) a partir de condições iniciais. Sem torques,
sem atrito: a energia mecânica deve ser conservada; a deriva numérica é reportada como validação.
Parâmetros padrão DEMONSTRATIVOS.
"""
from __future__ import annotations

import csv
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from biomechanics.force_engine.planar_dynamics import PlanarArm, Segment
from core.exceptions import NexusError
from research.experiments.bio001 import SOURCE_DEMO

EXPERIMENT_ID = "SIM-001"
MAX_STEPS = 2_000_000


class SimError(NexusError):
    pass


@dataclass
class PassiveParams:
    name: str = "Cadeia de 2 segmentos (DEMONSTRATIVO)"
    l1: float = 0.43
    m1: float = 7.0
    com1: float = 0.43
    l2: float = 0.43
    m2: float = 3.2
    com2: float = 0.43
    q1_deg: float = -30.0     # absoluto, medido do eixo x (−90° = pendurado)
    q2_deg: float = 20.0      # relativo
    qd1_deg_s: float = 0.0
    qd2_deg_s: float = 0.0
    t_end_s: float = 3.0
    dt_s: float = 1e-3
    source: str = SOURCE_DEMO

    def validate(self) -> None:
        for k in ("l1", "m1", "l2", "m2", "t_end_s", "dt_s"):
            if not getattr(self, k) > 0:
                raise SimError(f"{k} deve ser > 0")
        for k in ("com1", "com2"):
            if not 0 <= getattr(self, k) <= 1:
                raise SimError(f"{k} deve estar em [0, 1]")
        if self.t_end_s / self.dt_s > MAX_STEPS:
            raise SimError(f"Passos demais (> {MAX_STEPS}); aumente dt ou reduza a duração")
        if self.dt_s > 0.01:
            raise SimError("dt acima de 10 ms é instável/impreciso para este método")

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "PassiveParams":
        return PassiveParams(**d)


def run(p: PassiveParams, progress=None, should_cancel=None) -> dict:
    p.validate()
    arm = PlanarArm(Segment(p.l1, p.m1, p.com1), Segment(p.l2, p.m2, p.com2))
    r = math.radians
    T, X = arm.simulate([r(p.q1_deg), r(p.q2_deg)], [r(p.qd1_deg_s), r(p.qd2_deg_s)], p.t_end_s, p.dt_s,
                        progress=progress, should_cancel=should_cancel)
    E = np.array([arm.energy(x[:2], x[2:]) for x in X])
    scale = max(abs(E[0]), arm.s1.mass * arm.g * 0.1)
    drift = float(np.max(np.abs(E - E[0])) / scale)
    msgs = [f"Deriva máxima de energia: {drift:.3e} (relativa). "
            + ("OK." if drift < 1e-4 else "AVISO: reduza dt — deriva alta.")]
    msgs.append("Parâmetros demonstrativos: resultados ilustram o método, não anatomia real.")
    joint = np.array([arm.chain.forward(x[0], x[1])["joint"] for x in X])
    tip = np.array([arm.chain.forward(x[0], x[1])["tip"] for x in X])
    stride = max(1, -(-len(T) // 1000))  # teto: no máximo ~1000 pontos  # decimação só para animação/gráficos; energia e resumo usam todos os passos
    sl = slice(None, None, stride)
    a = {"name": p.name, "t": T[sl], "q": X[sl, :2], "qd": X[sl, 2:], "energy": E[sl],
         "joint_xy": joint[sl], "tip_xy": tip[sl],
         "summary": {"max_rel_energy_drift": drift, "energy_initial_j": float(E[0]), "energy_final_j": float(E[-1]),
                     "total_length_m": p.l1 + p.l2, "steps": int(len(T) - 1)}}
    return {"id": EXPERIMENT_ID, "params": p.to_dict(), "A": a, "messages": msgs}


def summary_dict(res: dict) -> dict:
    return {"A": res["A"]["summary"], "messages": res["messages"]}


def export_csv(res: dict, path: Path | str) -> None:
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    a = res["A"]
    try:
        with open(tmp, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["t_s", "q1_deg", "q2_deg", "qd1_deg_s", "qd2_deg_s", "energy_J", "tip_x_m", "tip_y_m"])
            for i, t in enumerate(a["t"]):
                w.writerow([f"{t:.6f}", *(f"{v:.9g}" for v in (*np.degrees(a["q"][i]), *np.degrees(a["qd"][i]),
                                                                  a["energy"][i], *a["tip_xy"][i]))])
        tmp.replace(path)
    except OSError as exc:
        raise SimError(f"Falha ao exportar CSV: {exc}") from exc

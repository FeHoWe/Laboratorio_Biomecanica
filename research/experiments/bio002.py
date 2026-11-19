"""BIO-002 — Comparative Joint Mechanics com 3 segmentos.

Modelo A: membro inferior humano simplificado (coxa, perna, pé). Modelo B: membro posterior animal
simplificado (fêmur, tíbia, metatarso; a 3ª junta representa o jarrete). Trajetória de mínimo jerk
por junta; torque por dinâmica inversa de Lagrange (cadeia de N segmentos). Parâmetros DEMONSTRATIVOS.
Ângulo q1 absoluto; q2, q3 relativos ao segmento anterior (graus nas entradas).
"""
from __future__ import annotations

import csv
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from biomechanics.force_engine.chain_dynamics import PlanarChain
from biomechanics.force_engine.planar_dynamics import G, Segment
from core.exceptions import NexusError
from research.experiments.bio001 import HYPOTHESES, SOURCE_DEMO, _trapz
from simulation.kinematics.planar import min_jerk

EXPERIMENT_ID = "BIO-002"


class Bio002Error(NexusError):
    pass


@dataclass
class ChainModel:
    name: str
    lengths_m: list[float]
    masses_kg: list[float]
    com_fracs: list[float]
    q_start_deg: list[float]
    q_end_deg: list[float]
    joint_names: list[str]
    tip_force_n: tuple[float, float] = (0.0, 0.0)
    source: str = SOURCE_DEMO

    def validate(self) -> None:
        n = len(self.lengths_m)
        if n < 2:
            raise Bio002Error(f"[{self.name}] ao menos 2 segmentos")
        for f in ("masses_kg", "com_fracs", "q_start_deg", "q_end_deg", "joint_names"):
            if len(getattr(self, f)) != n:
                raise Bio002Error(f"[{self.name}] '{f}' deve ter {n} elementos")
        if not all(v > 0 for v in self.lengths_m + self.masses_kg):
            raise Bio002Error(f"[{self.name}] comprimentos e massas devem ser > 0")
        if not all(0 <= c <= 1 for c in self.com_fracs):
            raise Bio002Error(f"[{self.name}] com_fracs deve estar em [0, 1]")
        if not all(math.isfinite(v) for v in self.q_start_deg + self.q_end_deg):
            raise Bio002Error(f"[{self.name}] ângulos inválidos")

    def chain(self) -> PlanarChain:
        return PlanarChain([Segment(l, m, c) for l, m, c in zip(self.lengths_m, self.masses_kg, self.com_fracs)])


@dataclass
class Bio002Params:
    model_a: ChainModel
    model_b: ChainModel
    duration_s: float = 1.0
    samples: int = 151

    def validate(self) -> None:
        if not self.duration_s > 0:
            raise Bio002Error("duration_s deve ser > 0")
        if not (isinstance(self.samples, int) and 5 <= self.samples <= 5001):
            raise Bio002Error("samples deve ser inteiro entre 5 e 5001")
        self.model_a.validate()
        self.model_b.validate()
        if len(self.model_a.lengths_m) != len(self.model_b.lengths_m):
            raise Bio002Error("Os modelos devem ter o mesmo número de segmentos")

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Bio002Params":
        def cm(x):
            x = dict(x)
            x["tip_force_n"] = tuple(x.get("tip_force_n", (0.0, 0.0)))
            return ChainModel(**x)
        return Bio002Params(cm(d["model_a"]), cm(d["model_b"]), float(d["duration_s"]), int(d["samples"]))


def default_params() -> Bio002Params:
    a = ChainModel("A — Membro inferior humano simplificado (3 seg.)", [0.43, 0.43, 0.24], [7.0, 3.2, 1.0],
                   [0.43, 0.43, 0.45], [-90, 0, 90], [-60, 60, 80], ["quadril", "joelho", "tornozelo"])
    b = ChainModel("B — Membro posterior animal simplificado (3 seg., jarrete)", [0.30, 0.30, 0.28], [2.0, 0.8, 0.5],
                   [0.45, 0.42, 0.45], [-90, 0, 0], [-55, -60, 40], ["quadril", "joelho", "jarrete"])
    return Bio002Params(a, b)


def _run_model(cfg: ChainModel, T: float, n: int) -> dict:
    chain = cfg.chain()
    N = chain.n
    r = math.radians
    traj = [min_jerk(r(s), r(e), T, n) for s, e in zip(cfg.q_start_deg, cfg.q_end_deg)]
    t = traj[0][0]
    q = np.column_stack([tr[1] for tr in traj])
    qd = np.column_stack([tr[2] for tr in traj])
    qdd = np.column_stack([tr[3] for tr in traj])
    tau = np.zeros((n, N))
    points = np.zeros((n, N + 1, 2))
    for i in range(n):
        tau[i] = chain.inverse_dynamics(q[i], qd[i], qdd[i], cfg.tip_force_n)
        points[i] = chain.points(q[i])
    power = tau * qd
    ref = float(chain.m.sum()) * G * float(chain.L.sum())
    pk = lambda a: [float(np.max(np.abs(a[:, k]))) for k in range(N)]
    return {"name": cfg.name, "joint_names": cfg.joint_names, "t": t, "q": q, "qd": qd, "qdd": qdd, "tau": tau,
            "power": power, "points": points, "tip_xy": points[:, -1, :], "joint_xy": points[:, 1, :],
            "summary": {"peak_abs_torque_nm": pk(tau), "peak_abs_ang_vel_rad_s": pk(qd), "peak_abs_power_w": pk(power),
                        "work_j": [_trapz(power[:, k], t) for k in range(N)], "total_mass_kg": float(chain.m.sum()),
                        "total_length_m": float(chain.L.sum()),
                        "peak_torque_normalized": [v / ref for v in pk(tau)]}}


def run(p: Bio002Params) -> dict:
    p.validate()
    ra, rb = (_run_model(c, p.duration_s, p.samples) for c in (p.model_a, p.model_b))
    msgs = []
    for r in (ra, rb):
        w = max(r["summary"]["peak_abs_ang_vel_rad_s"])
        if w > 20:
            msgs.append(f"AVISO [{r['name']}]: velocidade angular de pico {w:.1f} rad/s — verifique a duração.")
        if not np.all(np.isfinite(r["tau"])):
            raise Bio002Error(f"[{r['name']}] resultados não finitos")
    msgs.append("Parâmetros demonstrativos: resultados ilustram o método, não anatomia real.")
    comp = {}
    for key, label in (("peak_abs_torque_nm", "torque de pico (N·m)"),
                       ("peak_torque_normalized", "torque de pico normalizado (τ/(M·g·L))"),
                       ("peak_abs_ang_vel_rad_s", "velocidade angular de pico (rad/s)"),
                       ("peak_abs_power_w", "potência de pico (W)")):
        a, b = ra["summary"][key], rb["summary"][key]
        comp[key] = {"label": label, "A": a, "B": b, "ratio_B_over_A": [(y / x) if x > 0 else None for x, y in zip(a, b)]}
    return {"id": EXPERIMENT_ID, "params": p.to_dict(), "A": ra, "B": rb, "comparison": comp, "messages": msgs}


def summary_dict(res: dict) -> dict:
    return {"A": res["A"]["summary"], "B": res["B"]["summary"], "messages": res["messages"]}


def export_csv(res: dict, path: Path | str) -> None:
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    N = res["A"]["q"].shape[1]
    head = ["model", "t_s"] + [f"q{k+1}_deg" for k in range(N)] + [f"qd{k+1}_deg_s" for k in range(N)] + \
           [f"tau{k+1}_Nm" for k in range(N)] + [f"power{k+1}_W" for k in range(N)] + ["tip_x_m", "tip_y_m"]
    try:
        with open(tmp, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(head)
            for key in ("A", "B"):
                r = res[key]
                for i, t in enumerate(r["t"]):
                    w.writerow([key, f"{t:.6f}", *(f"{v:.9g}" for v in (*np.degrees(r["q"][i]), *np.degrees(r["qd"][i]),
                                                                            *r["tau"][i], *r["power"][i], *r["tip_xy"][i]))])
        tmp.replace(path)
    except OSError as exc:
        raise Bio002Error(f"Falha ao exportar CSV: {exc}") from exc


def report_markdown(res: dict) -> str:
    p = Bio002Params.from_dict(res["params"])
    L = [f"# Relatório técnico — {EXPERIMENT_ID} Comparative Joint Mechanics (3 segmentos)", "",
         "> Plataforma de pesquisa/aprendizado computacional. Não é dispositivo médico. Sem precisão clínica.", "",
         "## 1. Parâmetros de entrada (SI)", "", f"Duração: {p.duration_s} s; amostras: {p.samples}.", ""]
    for key, c in (("A", p.model_a), ("B", p.model_b)):
        L += [f"**Modelo {key}: {c.name}**  ", f"Origem dos parâmetros: {c.source}"]
        for i, jn in enumerate(c.joint_names):
            L.append(f"- Segmento {i+1} (junta: {jn}): L={c.lengths_m[i]} m, m={c.masses_kg[i]} kg, CM={c.com_fracs[i]}·L; "
                     f"q: {c.q_start_deg[i]}° → {c.q_end_deg[i]}°")
        L += [f"- Força externa na ponta: {tuple(c.tip_force_n)} N", ""]
    L += ["## 2. Hipóteses", ""] + [f"- {h}" for h in HYPOTHESES]
    L += ["", "## 3. Método", "", "Mínimo jerk por junta; dinâmica inversa de Lagrange para cadeia de N segmentos "
          "(M q̈ + C + G − Jᵀ F); potência = τ·q̇; trabalho por trapézios. Ver SIMULATION_METHODS.md.", "",
          "## 4. Resultados (por junta, na ordem dos segmentos)", ""]
    for c in res["comparison"].values():
        L.append(f"- {c['label']}: A = {[round(v, 4) for v in c['A']]}; B = {[round(v, 4) for v in c['B']]}")
    L += ["", "## 5. Mensagens de validação", ""] + [f"- {m}" for m in res["messages"]]
    L += ["", "## 6. Limitações", "", "- Modelo 2D simplificado, sem músculos, sem atrito, sem contato com o solo.",
          "- Parâmetros demonstrativos; sem equivalência anatômica entre A e B.", "- Resultados não validados experimentalmente.", ""]
    return "\n".join(L)

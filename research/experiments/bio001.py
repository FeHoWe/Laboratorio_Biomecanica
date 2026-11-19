"""BIO-001 — Comparative Joint Mechanics.

Compara dois mecanismos articulados planares de 2 segmentos, cada um percorrendo uma
trajetória de mínimo jerk entre posturas inicial e final. Calcula ângulos, velocidades,
acelerações, torques de junta (dinâmica inversa + força externa na ponta) e potências.

IMPORTANTE: os parâmetros padrão são DEMONSTRATIVOS (hipotéticos). Não derivam de fonte
científica verificada e não afirmam equivalência anatômica com estruturas biológicas reais.
"""
from __future__ import annotations

import csv
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from biomechanics.force_engine.planar_dynamics import G, PlanarArm, Segment
from core.exceptions import NexusError
from simulation.kinematics.planar import min_jerk

EXPERIMENT_ID = "BIO-001"
SOURCE_DEMO = "DEMONSTRATIVO (hipotético, sem fonte científica verificada)"

HYPOTHESES = [
    "Movimento planar no plano vertical; gravidade em -y (g = 9,80665 m/s²).",
    "Segmentos rígidos, homogêneos, com inércia de barra fina em torno do CM (m·L²/12) salvo indicação.",
    "Juntas rotativas ideais, sem atrito, sem músculos, sem folgas.",
    "Trajetória articular de mínimo jerk (quíntico) entre postura inicial e final.",
    "Força externa constante aplicada pelo ambiente na ponta distal; torque = M q̈ + C + G − Jᵀ F.",
    "Parâmetros dos modelos são demonstrativos e editáveis; não representam anatomia real.",
]


class ExperimentError(NexusError):
    pass


@dataclass
class ModelConfig:
    name: str
    l1: float                # m, segmento proximal
    m1: float                # kg
    com1: float              # fração do comprimento
    l2: float                # m, segmento distal
    m2: float                # kg
    com2: float
    q1_start_deg: float      # ângulo absoluto do segmento 1
    q1_end_deg: float
    q2_start_deg: float      # ângulo relativo do segmento 2 (junta intermediária)
    q2_end_deg: float
    tip_force_n: tuple[float, float] = (0.0, 0.0)  # N (Fx, Fy)
    source: str = SOURCE_DEMO

    def validate(self) -> None:
        for k in ("l1", "m1", "l2", "m2"):
            if not getattr(self, k) > 0:
                raise ExperimentError(f"[{self.name}] {k} deve ser > 0")
        for k in ("com1", "com2"):
            if not 0 <= getattr(self, k) <= 1:
                raise ExperimentError(f"[{self.name}] {k} deve estar em [0, 1]")
        for k in ("q1_start_deg", "q1_end_deg", "q2_start_deg", "q2_end_deg"):
            if not math.isfinite(getattr(self, k)):
                raise ExperimentError(f"[{self.name}] {k} inválido")

    def arm(self) -> PlanarArm:
        return PlanarArm(Segment(self.l1, self.m1, self.com1), Segment(self.l2, self.m2, self.com2))


@dataclass
class Bio001Params:
    model_a: ModelConfig
    model_b: ModelConfig
    duration_s: float = 1.0
    samples: int = 201

    def validate(self) -> None:
        if not self.duration_s > 0:
            raise ExperimentError("duration_s deve ser > 0")
        if not (isinstance(self.samples, int) and self.samples >= 5):
            raise ExperimentError("samples deve ser inteiro >= 5")
        self.model_a.validate()
        self.model_b.validate()

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Bio001Params":
        def mc(x: dict) -> ModelConfig:
            x = dict(x)
            x["tip_force_n"] = tuple(x.get("tip_force_n", (0.0, 0.0)))
            return ModelConfig(**x)
        return Bio001Params(mc(d["model_a"]), mc(d["model_b"]), float(d["duration_s"]), int(d["samples"]))


def default_params() -> Bio001Params:
    """Parâmetros DEMONSTRATIVOS. Modelo A: membro inferior humano simplificado (quadril→joelho→tornozelo).
    Modelo B: membro posterior animal simplificado (junta intermediária = jarrete)."""
    a = ModelConfig("A — Membro inferior humano simplificado", l1=0.43, m1=7.0, com1=0.43,
                    l2=0.43, m2=3.2, com2=0.43, q1_start_deg=-90, q1_end_deg=-60,
                    q2_start_deg=0, q2_end_deg=60)
    b = ModelConfig("B — Membro posterior animal simplificado (jarrete)", l1=0.30, m1=2.0, com1=0.45,
                    l2=0.28, m2=0.8, com2=0.40, q1_start_deg=-90, q1_end_deg=-55,
                    q2_start_deg=0, q2_end_deg=-70)
    return Bio001Params(a, b)


def _trapz(y: np.ndarray, x: np.ndarray) -> float:
    return float(np.sum((y[1:] + y[:-1]) * np.diff(x)) / 2.0)


def _run_model(cfg: ModelConfig, T: float, n: int) -> dict:
    arm = cfg.arm()
    d = math.radians
    t, q1, qd1, qdd1 = min_jerk(d(cfg.q1_start_deg), d(cfg.q1_end_deg), T, n)
    _, q2, qd2, qdd2 = min_jerk(d(cfg.q2_start_deg), d(cfg.q2_end_deg), T, n)
    F = np.asarray(cfg.tip_force_n, float)
    tau = np.zeros((n, 2))
    joint = np.zeros((n, 2))
    tip = np.zeros((n, 2))
    for i in range(n):
        tau[i] = arm.inverse_dynamics((q1[i], q2[i]), (qd1[i], qd2[i]), (qdd1[i], qdd2[i]))
        if F.any():
            tau[i] -= arm.chain.jacobian(q1[i], q2[i]).T @ F
        f = arm.chain.forward(q1[i], q2[i])
        joint[i], tip[i] = f["joint"], f["tip"]
    qd = np.column_stack([qd1, qd2])
    power = tau * qd
    M = cfg.m1 + cfg.m2
    Ltot = cfg.l1 + cfg.l2
    ref = M * G * Ltot  # N.m, escala de normalização (adimensional)
    return {
        "name": cfg.name, "t": t, "q": np.column_stack([q1, q2]), "qd": qd,
        "qdd": np.column_stack([qdd1, qdd2]), "tau": tau, "power": power,
        "joint_xy": joint, "tip_xy": tip,
        "summary": {
            "peak_abs_torque_nm": [float(np.max(np.abs(tau[:, k]))) for k in range(2)],
            "peak_abs_ang_vel_rad_s": [float(np.max(np.abs(qd[:, k]))) for k in range(2)],
            "peak_abs_power_w": [float(np.max(np.abs(power[:, k]))) for k in range(2)],
            "work_j": [_trapz(power[:, k], t) for k in range(2)],
            "total_mass_kg": M, "total_length_m": Ltot,
            "peak_torque_normalized": [float(np.max(np.abs(tau[:, k])) / ref) for k in range(2)],
        },
    }


def run(params: Bio001Params) -> dict:
    """Executa BIO-001. Determinístico: mesmos parâmetros -> mesmos resultados."""
    params.validate()
    ra = _run_model(params.model_a, params.duration_s, params.samples)
    rb = _run_model(params.model_b, params.duration_s, params.samples)
    messages = []
    for r in (ra, rb):
        w = max(r["summary"]["peak_abs_ang_vel_rad_s"])
        if w > 20:
            messages.append(f"AVISO [{r['name']}]: velocidade angular de pico {w:.1f} rad/s — "
                            "verifique a duração (movimento possivelmente irrealista).")
        if not np.all(np.isfinite(r["tau"])):
            raise ExperimentError(f"[{r['name']}] resultados não finitos")
    messages.append("Parâmetros demonstrativos: resultados ilustram o método, não anatomia real.")
    return {"id": EXPERIMENT_ID, "params": params.to_dict(), "A": ra, "B": rb,
            "comparison": compare(ra, rb), "messages": messages}


def compare(ra: dict, rb: dict) -> dict:
    out = {}
    for key, label in (("peak_abs_torque_nm", "torque de pico (N·m)"),
                       ("peak_torque_normalized", "torque de pico normalizado (τ/(M·g·L))"),
                       ("peak_abs_ang_vel_rad_s", "velocidade angular de pico (rad/s)"),
                       ("peak_abs_power_w", "potência de pico (W)")):
        a, b = ra["summary"][key], rb["summary"][key]
        out[key] = {"label": label, "A": a, "B": b,
                    "ratio_B_over_A": [(bb / aa) if aa > 0 else None for aa, bb in zip(a, b)]}
    return out


def summary_dict(result: dict) -> dict:
    """Resumo compacto (JSON-serializável) para guardar no projeto."""
    return {"A": result["A"]["summary"], "B": result["B"]["summary"], "messages": result["messages"]}


CSV_HEADER = ["model", "t_s", "q1_deg", "q2_deg", "qd1_deg_s", "qd2_deg_s", "qdd1_deg_s2", "qdd2_deg_s2",
              "tau1_Nm", "tau2_Nm", "power1_W", "power2_W", "joint_x_m", "joint_y_m", "tip_x_m", "tip_y_m"]


def export_csv(result: dict, path: Path | str) -> None:
    """CSV com unidades nos cabeçalhos. Escrita atômica."""
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(CSV_HEADER)
            for key in ("A", "B"):
                r = result[key]
                deg = np.degrees
                for i, t in enumerate(r["t"]):
                    w.writerow([key, f"{t:.6f}", *(f"{v:.9g}" for v in (
                        deg(r["q"][i, 0]), deg(r["q"][i, 1]), deg(r["qd"][i, 0]), deg(r["qd"][i, 1]),
                        deg(r["qdd"][i, 0]), deg(r["qdd"][i, 1]), r["tau"][i, 0], r["tau"][i, 1],
                        r["power"][i, 0], r["power"][i, 1], *r["joint_xy"][i], *r["tip_xy"][i]))])
        tmp.replace(path)
    except OSError as exc:
        raise ExperimentError(f"Falha ao exportar CSV: {exc}") from exc


def report_markdown(result: dict) -> str:
    p = Bio001Params.from_dict(result["params"])
    L = [f"# Relatório técnico — {EXPERIMENT_ID} Comparative Joint Mechanics", "",
         "> Plataforma de pesquisa/aprendizado computacional. Não é dispositivo médico. Sem precisão clínica.", "",
         "## 1. Parâmetros de entrada (SI)", "",
         f"Duração: {p.duration_s} s; amostras: {p.samples}.", ""]
    for key, cfg in (("A", p.model_a), ("B", p.model_b)):
        L += [f"**Modelo {key}: {cfg.name}**  ", f"Origem dos parâmetros: {cfg.source}",
              f"- Segmento 1: L={cfg.l1} m, m={cfg.m1} kg, CM={cfg.com1}·L",
              f"- Segmento 2: L={cfg.l2} m, m={cfg.m2} kg, CM={cfg.com2}·L",
              f"- q1: {cfg.q1_start_deg}° → {cfg.q1_end_deg}° (absoluto); q2: {cfg.q2_start_deg}° → {cfg.q2_end_deg}° (relativo)",
              f"- Força externa na ponta: {tuple(cfg.tip_force_n)} N", ""]
    L += ["## 2. Hipóteses", ""] + [f"- {h}" for h in HYPOTHESES]
    L += ["", "## 3. Método", "",
          "Trajetória de mínimo jerk; dinâmica inversa de Lagrange (M q̈ + C + G) menos Jᵀ F; potência = τ·q̇; "
          "trabalho por integração trapezoidal. Veja SIMULATION_METHODS.md.", "",
          "## 4. Resultados", "",
          "| Grandeza | A: junta 1 | A: junta 2 | B: junta 1 | B: junta 2 |", "|---|---|---|---|---|"]
    for key, c in result["comparison"].items():
        L.append(f"| {c['label']} | {c['A'][0]:.4g} | {c['A'][1]:.4g} | {c['B'][0]:.4g} | {c['B'][1]:.4g} |")
    L += ["", "## 5. Mensagens de validação", ""] + [f"- {m}" for m in result["messages"]]
    L += ["", "## 6. Limitações", "",
          "- Modelo 2D simplificado, sem músculos, sem atrito, sem contato com o solo.",
          "- Parâmetros demonstrativos; não há afirmação de equivalência anatômica entre A e B.",
          "- Resultados não validados experimentalmente.", ""]
    return "\n".join(L)

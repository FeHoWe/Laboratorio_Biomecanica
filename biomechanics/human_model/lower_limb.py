"""Modelo simplificado de membro inferior (plano sagital, exibido em 3D).

Convenção do mundo: x = anterior, y = para cima, z = lateral direita. Origem no solo sob o quadril.
Ângulos em graus na interface; flexão do quadril > 0 (coxa para frente), flexão do joelho > 0
(perna para trás), dorsiflexão do tornozelo > 0 (ponta do pé para cima). Neutro = 0/0/0: em pé.

TODOS os parâmetros padrão são DEMONSTRATIVOS (hipotéticos), sem fonte científica verificada.
Limites articulares são entradas configuráveis, não valores clínicos. O fíbula é apenas visual.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field

import numpy as np

from core.exceptions import NexusError
from core.geometry import transforms as T

SOURCE_DEMO = "DEMONSTRATIVO (hipotético, sem fonte científica verificada)"
ANKLE_HEIGHT = 0.08  # m, distância do eixo do tornozelo ao solo (demonstrativo)


class JointLimitError(NexusError):
    pass


class ModelError(NexusError):
    pass


@dataclass
class SegmentDef:
    name: str
    length_m: float
    mass_kg: float
    com_frac: float
    radius_m: float  # apenas visualização
    source: str = SOURCE_DEMO


@dataclass
class JointDef:
    name: str
    parent: str
    child: str
    min_deg: float
    max_deg: float
    description: str = ""


def _default_segments() -> dict[str, SegmentDef]:
    return {
        "pelvis": SegmentDef("pelvis", 0.18, 8.0, 0.5, 0.07),   # largura de quadril a quadril (visual)
        "femur": SegmentDef("femur", 0.43, 7.0, 0.43, 0.05),
        "tibia": SegmentDef("tibia", 0.40, 3.2, 0.43, 0.035),
        "fibula": SegmentDef("fibula", 0.36, 0.3, 0.43, 0.012),  # visual; massa pequena demonstrativa
        "foot": SegmentDef("foot", 0.24, 1.0, 0.45, 0.03),
    }


def _default_joints() -> dict[str, JointDef]:
    return {
        "hip": JointDef("hip", "pelvis", "femur", -20.0, 120.0, "flexão(+)/extensão(−)"),
        "knee": JointDef("knee", "femur", "tibia", 0.0, 140.0, "flexão(+)"),
        "ankle": JointDef("ankle", "tibia", "foot", -50.0, 30.0, "dorsiflexão(+)/plantiflexão(−)"),
    }


@dataclass
class LowerLimbModel:
    name: str = "Membro inferior simplificado (DEMONSTRATIVO)"
    segments: dict[str, SegmentDef] = field(default_factory=_default_segments)
    joints: dict[str, JointDef] = field(default_factory=_default_joints)
    angles_deg: dict[str, float] = field(default_factory=lambda: {"hip": 0.0, "knee": 0.0, "ankle": 0.0})

    # ---- configuração ----
    def validate(self) -> None:
        for s in self.segments.values():
            if not (s.length_m > 0 and s.mass_kg > 0 and 0 <= s.com_frac <= 1 and s.radius_m > 0):
                raise ModelError(f"Segmento inválido: {s.name}")
        for j in self.joints.values():
            if j.min_deg >= j.max_deg:
                raise ModelError(f"Limites inválidos em {j.name}: min >= max")
        for n, a in self.angles_deg.items():
            self._check(n, a)

    def _check(self, joint: str, deg: float) -> None:
        if joint not in self.joints:
            raise ModelError(f"Articulação desconhecida: {joint}")
        j = self.joints[joint]
        if not math.isfinite(deg) or not (j.min_deg - 1e-9 <= deg <= j.max_deg + 1e-9):
            raise JointLimitError(f"{joint}: {deg}° fora dos limites [{j.min_deg}, {j.max_deg}]°")

    def set_angle(self, joint: str, deg: float, clamp: bool = False) -> float:
        if clamp and joint in self.joints:
            j = self.joints[joint]
            deg = min(max(deg, j.min_deg), j.max_deg)
        self._check(joint, deg)
        self.angles_deg[joint] = float(deg)
        return float(deg)

    # ---- cinemática direta (matrizes homogêneas 4x4) ----
    def forward_kinematics(self) -> dict:
        """Posições mundiais (m) de quadril, joelho, tornozelo, ponta do pé e calcanhar + frames dos segmentos."""
        s, a = self.segments, {k: math.radians(v) for k, v in self.angles_deg.items()}
        hip_pos = np.array([0.0, s["femur"].length_m + s["tibia"].length_m + ANKLE_HEIGHT, 0.0])
        down = np.array([0.0, -1.0, 0.0])
        T_pelvis = T.homogeneous(None, hip_pos)
        T_femur = T.compose(T_pelvis, T.homogeneous(T.rot_z(a["hip"])))
        T_knee = T.compose(T_femur, T.homogeneous(None, down * s["femur"].length_m))
        T_tibia = T.compose(T_knee, T.homogeneous(T.rot_z(-a["knee"])))
        T_ankle = T.compose(T_tibia, T.homogeneous(None, down * s["tibia"].length_m))
        T_foot = T.compose(T_ankle, T.homogeneous(T.rot_z(a["ankle"])))
        x_axis = np.array([1.0, 0.0, 0.0])
        return {
            "frames": {"pelvis": T_pelvis, "femur": T_femur, "tibia": T_tibia, "foot": T_foot},
            "hip": hip_pos, "knee": T_knee[:3, 3].copy(), "ankle": T_ankle[:3, 3].copy(),
            "toe": T.apply(T_foot, x_axis * s["foot"].length_m),
            "heel": T.apply(T_foot, -x_axis * 0.06),
        }

    def segment_endpoints(self) -> dict[str, tuple[np.ndarray, np.ndarray]]:
        fk = self.forward_kinematics()
        z = np.array([0.0, 0.0, 1.0])
        half = self.segments["pelvis"].length_m / 2
        d = {"pelvis": (fk["hip"] - z * half, fk["hip"] + z * half),
             "femur": (fk["hip"], fk["knee"]), "tibia": (fk["knee"], fk["ankle"]),
             "foot": (fk["ankle"], fk["toe"])}
        # fíbula: paralela à tíbia, deslocada lateralmente (apenas visual)
        off = z * (self.segments["tibia"].radius_m + self.segments["fibula"].radius_m + 0.004)
        L = self.segments["fibula"].length_m / self.segments["tibia"].length_m
        t0, t1 = d["tibia"]
        d["fibula"] = (t0 + (t1 - t0) * (1 - L) + off, t1 + off)
        return d

    def total_com(self) -> np.ndarray:
        """CM do membro (sem pelve: massa da pelve não pertence ao membro) em coordenadas mundiais."""
        ep = self.segment_endpoints()
        m, pts = [], []
        for name in ("femur", "tibia", "foot"):
            seg = self.segments[name]
            p0, p1 = ep[name]
            m.append(seg.mass_kg)
            pts.append(p0 + (p1 - p0) * seg.com_frac)
        m = np.asarray(m)
        return (m[:, None] * np.asarray(pts)).sum(axis=0) / m.sum()

    # ---- serialização ----
    def to_dict(self) -> dict:
        return {"name": self.name, "type": "lower_limb", "segments": {k: asdict(v) for k, v in self.segments.items()},
                "joints": {k: asdict(v) for k, v in self.joints.items()}, "angles_deg": dict(self.angles_deg)}

    @staticmethod
    def from_dict(d: dict) -> "LowerLimbModel":
        m = LowerLimbModel(d["name"], {k: SegmentDef(**v) for k, v in d["segments"].items()},
                           {k: JointDef(**v) for k, v in d["joints"].items()}, dict(d["angles_deg"]))
        m.validate()
        return m

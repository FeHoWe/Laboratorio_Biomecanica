"""Articulações espaciais, independentes da interface gráfica.

Toda junta é uma composição de graus de liberdade elementares (revolução em torno de um eixo ou translação ao longo dele):
    T_pai←filho(q) = T_origem · M₁(q₁) · M₂(q₂) · …
- T_origem: posição/orientação do referencial da junta no referencial do corpo pai.
- Eixos dos DOFs são dados no referencial da junta e SEGUEM os DOFs anteriores (rotações intrínsecas).
Tipos: revolute (1 DOF), universal (2 DOFs de rotação em sequência, eixos não paralelos), spherical (3 DOFs de rotação em sequência — Tait-Bryan; singular quando o DOF do meio atinge ±90°
se os três eixos forem ortogonais; limites configuráveis devem evitar isso), prismatic (1 DOF), fixed (0 DOF).
Unidades: rad (rotação) e m (translação).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from biomechanics.spatial import transforms as T
from biomechanics.spatial.rotations import RotationError, unit
from core.exceptions import NexusError

JOINT_TYPES = ("revolute", "universal", "spherical", "prismatic", "fixed")


class JointError(NexusError):
    pass


@dataclass
class Dof:
    name: str
    kind: str                 # "revolute" | "prismatic"
    axis: list                # unitário, no referencial da junta
    min: float                # rad ou m
    max: float

    def validate(self) -> None:
        if self.kind not in ("revolute", "prismatic"):
            raise JointError(f"DOF {self.name}: tipo inválido {self.kind}")
        try:
            a = unit(self.axis)
        except RotationError as exc:
            raise JointError(f"DOF {self.name}: eixo inválido ({exc})") from exc
        self.axis = [float(x) for x in a]
        if not (np.isfinite(self.min) and np.isfinite(self.max) and self.min < self.max):
            raise JointError(f"DOF {self.name}: limites inválidos (min deve ser < max)")

    def motion(self, q: float) -> np.ndarray:
        if self.kind == "revolute":
            return T.make(T.rotation_about(self.axis, q)[:3, :3])
        return T.translation_along(self.axis, q)


@dataclass
class SpatialJoint:
    name: str
    jtype: str
    parent: str
    child: str
    dofs: list = field(default_factory=list)
    origin: list = field(default_factory=lambda: np.eye(4).tolist())   # 4x4: referencial da junta no corpo pai

    @property
    def n_dof(self) -> int:
        return len(self.dofs)

    def origin_T(self) -> np.ndarray:
        return np.asarray(self.origin, float)

    def validate(self) -> None:
        if self.jtype not in JOINT_TYPES:
            raise JointError(f"{self.name}: tipo de junta inválido ({self.jtype})")
        if not (self.parent and self.child) or self.parent == self.child:
            raise JointError(f"{self.name}: pai e filho devem ser corpos distintos")
        if not T.is_transform(self.origin_T()):
            raise JointError(f"{self.name}: origem não é uma transformação rígida válida")
        expected = {"revolute": 1, "prismatic": 1, "universal": 2, "spherical": 3, "fixed": 0}[self.jtype]
        if self.n_dof != expected:
            raise JointError(f"{self.name}: junta {self.jtype} exige {expected} DOF(s), recebeu {self.n_dof}")
        for d in self.dofs:
            d.validate()
        kinds = {"revolute": "revolute", "universal": "revolute", "spherical": "revolute", "prismatic": "prismatic"}
        for d in self.dofs:
            if self.jtype != "fixed" and d.kind != kinds[self.jtype]:
                raise JointError(f"{self.name}: DOF {d.name} incompatível com junta {self.jtype}")
        if self.jtype in ("spherical", "universal"):
            ax = [np.asarray(d.axis) for d in self.dofs]
            for a, b in zip(ax[:-1], ax[1:]):
                if np.linalg.norm(np.cross(a, b)) < 1e-9:
                    raise JointError(f"{self.name}: eixos consecutivos paralelos (a junta perderia graus de liberdade)")

    def transform(self, q) -> np.ndarray:
        """T_pai←filho para os valores q (len = n_dof)."""
        q = np.atleast_1d(np.asarray(q, float))
        if q.shape != (self.n_dof,):
            raise JointError(f"{self.name}: esperados {self.n_dof} valor(es), recebido {q.shape}")
        out = self.origin_T()
        for d, v in zip(self.dofs, q):
            out = out @ d.motion(float(v))
        return out

    def limits(self) -> tuple[np.ndarray, np.ndarray]:
        return (np.array([d.min for d in self.dofs]), np.array([d.max for d in self.dofs]))

    def violations(self, q, tol: float = 1e-9) -> list[str]:
        lo, hi = self.limits()
        q = np.atleast_1d(np.asarray(q, float))
        return [f"{self.name}/{d.name}: {v:.4g} fora de [{d.min:.4g}, {d.max:.4g}]"
                for d, v in zip(self.dofs, q) if v < d.min - tol or v > d.max + tol]

    def gimbal_margin(self, q) -> float | None:
        """Só para juntas esféricas com eixos ortogonais entre si: |cos(DOF do meio)|; 0 = singularidade."""
        if self.jtype != "spherical":
            return None
        ax = [np.asarray(d.axis) for d in self.dofs]
        if not (abs(ax[0] @ ax[1]) < 1e-9 and abs(ax[1] @ ax[2]) < 1e-9 and abs(ax[0] @ ax[2]) < 1e-9):
            return None
        return float(abs(np.cos(np.atleast_1d(q)[1])))

    def to_dict(self) -> dict:
        return {"name": self.name, "jtype": self.jtype, "parent": self.parent, "child": self.child,
                "origin": [[float(x) for x in r] for r in self.origin_T()],
                "dofs": [{"name": d.name, "kind": d.kind, "axis": [float(x) for x in d.axis], "min": d.min, "max": d.max}
                         for d in self.dofs]}

    @staticmethod
    def from_dict(d: dict) -> "SpatialJoint":
        try:
            j = SpatialJoint(d["name"], d["jtype"], d["parent"], d["child"],
                             [Dof(x["name"], x["kind"], list(x["axis"]), float(x["min"]), float(x["max"])) for x in d["dofs"]],
                             [list(r) for r in d["origin"]])
        except (KeyError, TypeError, ValueError) as exc:
            raise JointError(f"Junta inválida: {exc}") from exc
        j.validate()
        return j


def _origin(position, rotation=None) -> list:
    return T.make(rotation, position).tolist()


def revolute(name, parent, child, axis, position, limits_rad=(-np.pi, np.pi), dof_name=None, rotation=None) -> SpatialJoint:
    j = SpatialJoint(name, "revolute", parent, child, [Dof(dof_name or name, "revolute", list(axis), *limits_rad)],
                     _origin(position, rotation))
    j.validate()
    return j


def prismatic(name, parent, child, axis, position, limits_m=(-1.0, 1.0), rotation=None) -> SpatialJoint:
    j = SpatialJoint(name, "prismatic", parent, child, [Dof(name, "prismatic", list(axis), *limits_m)], _origin(position, rotation))
    j.validate()
    return j


def spherical(name, parent, child, position, axes=((0, 0, 1), (1, 0, 0), (0, 1, 0)), limits_rad=None,
              dof_names=None, rotation=None) -> SpatialJoint:
    limits_rad = limits_rad or [(-np.pi, np.pi)] * 3
    dof_names = dof_names or [f"{name}_{i + 1}" for i in range(3)]
    j = SpatialJoint(name, "spherical", parent, child,
                     [Dof(n, "revolute", list(a), *lim) for n, a, lim in zip(dof_names, axes, limits_rad)],
                     _origin(position, rotation))
    j.validate()
    return j


def universal(name, parent, child, position, axes=((0, 0, 1), (1, 0, 0)), limits_rad=None, dof_names=None,
              rotation=None) -> SpatialJoint:
    limits_rad = limits_rad or [(-np.pi, np.pi)] * 2
    dof_names = dof_names or [f"{name}_{i + 1}" for i in range(2)]
    j = SpatialJoint(name, "universal", parent, child,
                     [Dof(n, "revolute", list(a), *lim) for n, a, lim in zip(dof_names, axes, limits_rad)],
                     _origin(position, rotation))
    j.validate()
    return j


def fixed(name, parent, child, position, rotation=None) -> SpatialJoint:
    j = SpatialJoint(name, "fixed", parent, child, [], _origin(position, rotation))
    j.validate()
    return j

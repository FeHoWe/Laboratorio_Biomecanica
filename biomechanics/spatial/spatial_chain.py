"""Cadeia articulada espacial (árvore de corpos rígidos ligados por juntas), com cinemática direta.

Vetor de coordenadas generalizadas q: concatenação dos DOFs das juntas, na ordem em que as juntas foram fornecidas
(que deve ser topológica: o pai de cada junta aparece antes). O corpo `base` é fixo no mundo com a transformação `base_T`.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from biomechanics.spatial import transforms as T
from biomechanics.spatial.rigid_body import RigidBody
from biomechanics.spatial.spatial_joints import JointError, SpatialJoint
from core.exceptions import NexusError


class ChainError(NexusError):
    pass


@dataclass
class FKResult:
    T: dict            # id do corpo -> T_mundo←corpo (4x4)
    axis: np.ndarray   # (n, 3) eixo de cada DOF no mundo
    origin: np.ndarray  # (n, 3) ponto do eixo (origem do referencial do DOF) no mundo
    kind: list         # "revolute"/"prismatic" por DOF
    body_of_dof: list  # corpo filho da junta a que cada DOF pertence


class SpatialChain:
    def __init__(self, name: str, bodies: list, joints: list, base: str, base_T=None) -> None:
        self.name = name
        self.bodies: dict[str, RigidBody] = {}
        for b in bodies:
            b.validate()
            if b.id in self.bodies:
                raise ChainError(f"Corpo duplicado: {b.id}")
            self.bodies[b.id] = b
        if base not in self.bodies:
            raise ChainError(f"Corpo base desconhecido: {base}")
        self.base = base
        self.base_T = np.eye(4) if base_T is None else np.asarray(base_T, float)
        if not T.is_transform(self.base_T):
            raise ChainError("base_T não é uma transformação rígida válida")
        self.joints: list[SpatialJoint] = list(joints)
        self._build()
        self.q = np.zeros(self.n_dof)

    # ---- estrutura ----
    def _build(self) -> None:
        seen = {self.base}
        self.joint_slices: dict[str, slice] = {}
        self.dofs = []
        self.parent_joint: dict[str, int] = {}
        names = set()
        for ji, j in enumerate(self.joints):
            j.validate()
            if j.name in names:
                raise ChainError(f"Junta duplicada: {j.name}")
            names.add(j.name)
            for bid in (j.parent, j.child):
                if bid not in self.bodies:
                    raise ChainError(f"Junta {j.name}: corpo desconhecido {bid}")
            if j.parent not in seen:
                raise ChainError(f"Junta {j.name}: o corpo pai '{j.parent}' ainda não está conectado à base "
                                 "(ordem das juntas deve ser topológica; ciclos não são permitidos)")
            if j.child in seen:
                raise ChainError(f"Corpo '{j.child}' tem mais de uma junta pai (ou forma ciclo)")
            seen.add(j.child)
            self.parent_joint[j.child] = ji
            self.joint_slices[j.name] = slice(len(self.dofs), len(self.dofs) + j.n_dof)
            self.dofs += [(j.name, d) for d in j.dofs]
        orphans = set(self.bodies) - seen
        if orphans:
            raise ChainError(f"Corpos sem junta que os conecte à base: {sorted(orphans)}")

    @property
    def n_dof(self) -> int:
        return len(self.dofs)

    def dof_names(self) -> list[str]:
        return [d.name for _, d in self.dofs]

    def limits(self) -> tuple[np.ndarray, np.ndarray]:
        return (np.array([d.min for _, d in self.dofs]), np.array([d.max for _, d in self.dofs]))

    def moving_bodies(self) -> list[str]:
        return [j.child for j in self.joints]

    def dof_path(self, body: str) -> list[int]:
        """Índices de DOFs (ordenados da base para o corpo) que movem o corpo."""
        if body not in self.bodies:
            raise ChainError(f"Corpo desconhecido: {body}")
        idx: list[int] = []
        cur = body
        while cur != self.base:
            j = self.joints[self.parent_joint[cur]]
            sl = self.joint_slices[j.name]
            idx = list(range(sl.start, sl.stop)) + idx
            cur = j.parent
        return idx

    def check_q(self, q) -> np.ndarray:
        q = np.asarray(q, float)
        if q.shape != (self.n_dof,) or not np.all(np.isfinite(q)):
            raise ChainError(f"q deve ter {self.n_dof} valores finitos")
        return q

    def violations(self, q) -> list[str]:
        q = self.check_q(q)
        out: list[str] = []
        for j in self.joints:
            out += j.violations(q[self.joint_slices[j.name]])
        return out

    # ---- cinemática direta ----
    def forward_kinematics(self, q) -> FKResult:
        q = self.check_q(q)
        Tw = {self.base: self.base_T.copy()}
        axis = np.zeros((self.n_dof, 3))
        origin = np.zeros((self.n_dof, 3))
        kind, owner = [], []
        for j in self.joints:
            cur = Tw[j.parent] @ j.origin_T()
            sl = self.joint_slices[j.name]
            for k, d, v in zip(range(sl.start, sl.stop), j.dofs, q[sl]):
                axis[k] = cur[:3, :3] @ np.asarray(d.axis)
                origin[k] = cur[:3, 3]
                kind.append(d.kind)
                owner.append(j.child)
                cur = cur @ d.motion(float(v))
            Tw[j.child] = cur
        return FKResult(Tw, axis, origin, kind, owner)

    def com_world(self, body: str, fk: FKResult) -> np.ndarray:
        return T.apply(fk.T[body], self.bodies[body].com)

    def point_world(self, body: str, p_local, fk: FKResult) -> np.ndarray:
        return T.apply(fk.T[body], p_local)

    def total_mass(self, moving_only: bool = True) -> float:
        ids = self.moving_bodies() if moving_only else list(self.bodies)
        return float(sum(self.bodies[i].mass_kg for i in ids))

    def total_com(self, q, moving_only: bool = True) -> np.ndarray:
        fk = self.forward_kinematics(q)
        ids = self.moving_bodies() if moving_only else list(self.bodies)
        m = np.array([self.bodies[i].mass_kg for i in ids])
        c = np.array([self.com_world(i, fk) for i in ids])
        return (m[:, None] * c).sum(axis=0) / m.sum()

    # ---- serialização ----
    def to_dict(self) -> dict:
        return {"name": self.name, "type": "spatial_chain", "base": self.base,
                "base_T": [[float(x) for x in r] for r in self.base_T],
                "bodies": [b.to_dict() for b in self.bodies.values()], "joints": [j.to_dict() for j in self.joints],
                "q_rad": [float(x) for x in self.q]}

    @staticmethod
    def from_dict(d: dict) -> "SpatialChain":
        try:
            ch = SpatialChain(d["name"], [RigidBody.from_dict(b) for b in d["bodies"]],
                              [SpatialJoint.from_dict(j) for j in d["joints"]], d["base"], d.get("base_T"))
            if "q_rad" in d:
                ch.q = ch.check_q(d["q_rad"])
        except (KeyError, TypeError) as exc:
            raise ChainError(f"Cadeia espacial inválida: {exc}") from exc
        except JointError as exc:
            raise ChainError(str(exc)) from exc
        return ch

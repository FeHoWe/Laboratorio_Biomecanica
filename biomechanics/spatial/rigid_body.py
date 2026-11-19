"""Corpo rígido (segmento): identificador, nome, comprimento, massa, CM e tensor de inércia no referencial local.

Referencial local do corpo: origem na articulação proximal; o eixo do segmento é definido pela geometria visual.
Inércia: tensor 3x3 (kg·m²) em torno do CENTRO DE MASSA, expresso nos eixos locais.
Categorias de confiabilidade: DEMONSTRATIVO (hipotético), ESTIMADO (calculado a partir de outros dados do usuário),
REFERENCIADO (exige fonte). Parâmetros DEMONSTRATIVOS nunca devem ser apresentados como anatomia real.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from core.exceptions import NexusError

RELIABILITY = ("DEMONSTRATIVO", "ESTIMADO", "REFERENCIADO")
SOURCE_DEMO = "DEMONSTRATIVO (hipotético, sem fonte científica verificada)"


class RigidBodyError(NexusError):
    pass


def cylinder_inertia(mass: float, length: float, radius: float, axis: int = 1) -> np.ndarray:
    """Cilindro maciço homogêneo, eixo ao longo de `axis` (0=x,1=y,2=z), em torno do CM:
    I_eixo = m r²/2;  I_transversal = m (3r² + L²)/12."""
    ia = 0.5 * mass * radius ** 2
    it = mass * (3 * radius ** 2 + length ** 2) / 12.0
    d = [it, it, it]
    d[axis] = ia
    return np.diag(d)


def parallel_axis(I_com: np.ndarray, mass: float, d) -> np.ndarray:
    """Teorema dos eixos paralelos: I_O = I_cm + m (|d|² I − d dᵀ)."""
    d = np.asarray(d, float)
    return I_com + mass * (float(d @ d) * np.eye(3) - np.outer(d, d))


@dataclass
class RigidBody:
    id: str
    name: str
    length_m: float
    mass_kg: float
    com_local_m: list            # [x, y, z] no referencial local (m)
    inertia_kg_m2: list          # 3x3 em torno do CM, eixos locais
    visual: dict = field(default_factory=dict)   # {"shape": "cylinder", "radius_m": r, "p0": [...], "p1": [...]}
    source: str = SOURCE_DEMO
    reliability: str = "DEMONSTRATIVO"

    @property
    def inertia(self) -> np.ndarray:
        return np.asarray(self.inertia_kg_m2, float)

    @property
    def com(self) -> np.ndarray:
        return np.asarray(self.com_local_m, float)

    def validate(self) -> None:
        if not (self.id and self.name):
            raise RigidBodyError("Corpo precisa de id e nome")
        if not (np.isfinite(self.length_m) and self.length_m > 0 and np.isfinite(self.mass_kg) and self.mass_kg > 0):
            raise RigidBodyError(f"{self.id}: comprimento e massa devem ser > 0")
        com, I = self.com, self.inertia
        if com.shape != (3,) or not np.all(np.isfinite(com)):
            raise RigidBodyError(f"{self.id}: CM inválido")
        if I.shape != (3, 3) or not np.all(np.isfinite(I)) or not np.allclose(I, I.T, atol=1e-12):
            raise RigidBodyError(f"{self.id}: tensor de inércia deve ser 3x3 simétrico")
        w = np.linalg.eigvalsh(I)
        if w[0] <= 0:
            raise RigidBodyError(f"{self.id}: tensor de inércia deve ser definido positivo")
        if w[2] > w[0] + w[1] + 1e-12:  # desigualdade triangular dos momentos principais
            raise RigidBodyError(f"{self.id}: momentos principais violam a desigualdade triangular (fisicamente impossível)")
        if self.reliability not in RELIABILITY:
            raise RigidBodyError(f"{self.id}: confiabilidade deve ser uma de {RELIABILITY}")
        if self.reliability == "REFERENCIADO" and (not self.source or self.source == SOURCE_DEMO):
            raise RigidBodyError(f"{self.id}: parâmetros REFERENCIADO exigem a fonte")

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "length_m": self.length_m, "mass_kg": self.mass_kg,
                "com_local_m": [float(x) for x in self.com], "inertia_kg_m2": [[float(x) for x in r] for r in self.inertia],
                "visual": self.visual, "source": self.source, "reliability": self.reliability}

    @staticmethod
    def from_dict(d: dict) -> "RigidBody":
        try:
            b = RigidBody(d["id"], d["name"], float(d["length_m"]), float(d["mass_kg"]), list(d["com_local_m"]),
                          [list(r) for r in d["inertia_kg_m2"]], dict(d.get("visual", {})),
                          d.get("source", SOURCE_DEMO), d.get("reliability", "DEMONSTRATIVO"))
        except (KeyError, TypeError, ValueError) as exc:
            raise RigidBodyError(f"Corpo rígido inválido: {exc}") from exc
        b.validate()
        return b

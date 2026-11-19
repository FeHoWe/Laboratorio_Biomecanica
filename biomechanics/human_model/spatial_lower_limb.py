"""Membro inferior espacial (DEMONSTRATIVO): pelve (base fixa), fêmur, tíbia, fíbula (fixa à tíbia) e pé.

Reaproveita os parâmetros de segmentos do LowerLimbModel sagital (comprimentos, massas, CM, raios) e os limites de
quadril/joelho/tornozelo. Convenção idêntica à do modelo antigo (x anterior, y cima, z lateral):
  DOFs (ordem de q): [quadril flexão (eixo +z), quadril abdução (eixo x), quadril rotação (eixo y),
                      joelho flexão (eixo −z), tornozelo dorsiflexão (eixo +z), tornozelo inversão (eixo x)]
Com abdução = rotação = inversão = 0, as posições coincidem com as de LowerLimbModel (verificado por teste).
Quadril = 3 DOFs rotacionais (sequência Z-X-Y); joelho = 1 DOF; tornozelo = 2 DOFs. SIMPLIFICAÇÕES MECÂNICAS: não
reproduzem integralmente a anatomia articular. Inércias: cilindros homogêneos (DEMONSTRATIVO). Limites de abdução/rotação/
inversão são entradas configuráveis hipotéticas.
"""
from __future__ import annotations

import math

import numpy as np

from biomechanics.human_model.lower_limb import ANKLE_HEIGHT, LowerLimbModel
from biomechanics.spatial import transforms as T
from biomechanics.spatial.rigid_body import SOURCE_DEMO, RigidBody, cylinder_inertia
from biomechanics.spatial.spatial_chain import SpatialChain
from biomechanics.spatial.spatial_joints import fixed, revolute, spherical, universal

DOF_NAMES = ["quadril_flexao", "quadril_abducao", "quadril_rotacao", "joelho_flexao", "tornozelo_dorsiflexao", "tornozelo_inversao"]
EXTRA_LIMITS_DEG = {"hip_abd": (-30.0, 40.0), "hip_rot": (-35.0, 35.0), "ankle_inv": (-20.0, 20.0)}  # hipotéticos


def build_spatial_lower_limb(model: LowerLimbModel | None = None, extra_limits_deg: dict | None = None) -> SpatialChain:
    m = model or LowerLimbModel()
    s, j = m.segments, m.joints
    ex = {**EXTRA_LIMITS_DEG, **(extra_limits_deg or {})}
    rad = math.radians
    lf, lt, lfoot, lfib = s["femur"].length_m, s["tibia"].length_m, s["foot"].length_m, s["fibula"].length_m
    half = s["pelvis"].length_m / 2

    def seg_body(bid, name, seg, axis_dir, length):
        d = np.asarray(axis_dir, float)
        ax = int(np.argmax(np.abs(d)))
        return RigidBody(bid, name, length, seg.mass_kg, (d * seg.com_frac * length).tolist(),
                         cylinder_inertia(seg.mass_kg, length, seg.radius_m, ax).tolist(),
                         {"shape": "cylinder", "radius_m": seg.radius_m, "p0": [0, 0, 0], "p1": (d * length).tolist()}, SOURCE_DEMO)

    pelvis = RigidBody("pelvis", "Pelve", 2 * half, s["pelvis"].mass_kg, [0, 0, 0],
                       cylinder_inertia(s["pelvis"].mass_kg, 2 * half, s["pelvis"].radius_m, 2).tolist(),
                       {"shape": "cylinder", "radius_m": s["pelvis"].radius_m, "p0": [0, 0, -half], "p1": [0, 0, half]}, SOURCE_DEMO)
    femur = seg_body("femur", "Fêmur", s["femur"], [0, -1, 0], lf)
    tibia = seg_body("tibia", "Tíbia", s["tibia"], [0, -1, 0], lt)
    fibula = seg_body("fibula", "Fíbula", s["fibula"], [0, -1, 0], lfib)
    foot = seg_body("foot", "Pé", s["foot"], [1, 0, 0], lfoot)
    off = s["tibia"].radius_m + s["fibula"].radius_m + 0.004
    hip_lim = [(rad(j["hip"].min_deg), rad(j["hip"].max_deg)), (rad(ex["hip_abd"][0]), rad(ex["hip_abd"][1])),
               (rad(ex["hip_rot"][0]), rad(ex["hip_rot"][1]))]
    joints = [
        spherical("quadril", "pelvis", "femur", [0, 0, 0], ((0, 0, 1), (1, 0, 0), (0, 1, 0)), hip_lim, DOF_NAMES[0:3]),
        revolute("joelho", "femur", "tibia", [0, 0, -1], [0, -lf, 0], (rad(j["knee"].min_deg), rad(j["knee"].max_deg)), DOF_NAMES[3]),
        fixed("fibula_fixa", "tibia", "fibula", [0, -(lt - lfib), off]),
        universal("tornozelo", "tibia", "foot", [0, -lt, 0], ((0, 0, 1), (1, 0, 0)),
                  [(rad(j["ankle"].min_deg), rad(j["ankle"].max_deg)), (rad(ex["ankle_inv"][0]), rad(ex["ankle_inv"][1]))],
                  DOF_NAMES[4:6]),
    ]
    base_T = T.make(None, [0.0, lf + lt + ANKLE_HEIGHT, 0.0])
    return SpatialChain("Membro inferior espacial (DEMONSTRATIVO)", [pelvis, femur, tibia, fibula, foot], joints, "pelvis", base_T)

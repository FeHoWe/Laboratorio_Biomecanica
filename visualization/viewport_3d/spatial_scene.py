"""Cena 3D dinâmica para SpatialChain (PyVista/VTK). Independente de Qt.

Estratégia: cada corpo é um ator criado UMA vez com geometria em coordenadas locais; a cada quadro só se atualiza
`actor.user_matrix = T_mundo←corpo` (sem recriar atores). Vetores de força/torque e trajetória reaproveitam PolyData com copy_from.
Mostra: segmentos, juntas, orientação (eixos locais), CM por corpo, CM total, vetores (torque articular como seta no eixo, força
externa), trajetória de um ponto, seleção e câmeras. Só desenha estados recebidos (q de uma Trajectory ou pose configurada).
"""
from __future__ import annotations

import numpy as np
import pyvista as pv

from biomechanics.spatial import transforms as T
from biomechanics.spatial.spatial_chain import SpatialChain
from visualization.viewport_3d.scene import SELECT_COLOR, cylinder_between

BODY_COLORS = {"pelvis": "#8892a6", "femur": "#2389FF", "tibia": "#19C7D9", "fibula": "#7fdde6", "foot": "#E8EDF5"}
DEFAULT_COLOR = "#9fb3d1"
AXIS_COLORS = (("x", (1, 0, 0), "#ff5c6c"), ("y", (0, 1, 0), "#3dd68c"), ("z", (0, 0, 1), "#2389ff"))
CAMERA_PRESETS = {"isometrica": ((2.2, 1.4, 2.6), (0.1, 0.6, 0.0), (0, 1, 0)),
                  "lateral": ((0.1, 0.6, 3.0), (0.1, 0.6, 0.0), (0, 1, 0)),       # olhando ao longo de −z: plano sagital (x-y)
                  "frontal": ((3.0, 0.6, 0.0), (0.1, 0.6, 0.0), (0, 1, 0)),
                  "superior": ((0.1, 3.2, 0.001), (0.1, 0.0, 0.0), (1, 0, 0))}


def vector_arrow(origin, vec, scale: float = 1.0, min_len: float = 1e-6):
    """Seta de `origin` na direção de `vec` com comprimento scale·|vec| (None se |vec| ≈ 0)."""
    v = np.asarray(vec, float) * scale
    n = float(np.linalg.norm(v))
    if n < min_len:
        return None
    return pv.Arrow(start=np.asarray(origin, float), direction=v / n, scale=n, tip_length=0.25, tip_radius=0.06, shaft_radius=0.02)


class SpatialScene:
    def __init__(self, plotter, show_axes: bool = True, show_com: bool = True) -> None:
        self.plotter = plotter
        self.chain: SpatialChain | None = None
        self.actors: dict[str, object] = {}
        self.axis_actors: dict[str, list] = {}
        self.com_actors: dict[str, object] = {}
        self.joint_actors: dict[str, object] = {}
        self.meshes: dict[str, pv.PolyData] = {}
        self.selected: str | None = None
        self.show_axes, self.show_com = show_axes, show_com
        self.trajectory_pts: list = []
        self._static = False
        self.q = None
        self.n_actor_creations = 0

    # ---- construção (uma vez) ----
    def _static_scene(self) -> None:
        p = self.plotter
        p.set_background("#10141C")
        p.add_mesh(pv.Plane(center=(0.15, 0, 0), direction=(0, 1, 0), i_size=1.4, j_size=1.4, i_resolution=14, j_resolution=14),
                   style="wireframe", color="#2a3548", line_width=1, name="ground")
        for nm, d, c in AXIS_COLORS:
            p.add_mesh(pv.Arrow(start=(0, 0, 0), direction=d, scale=0.25, tip_radius=0.05, shaft_radius=0.02), color=c, name=f"w_axis_{nm}")
        p.add_axes(color="white")
        self._static = True

    def set_chain(self, chain: SpatialChain, q=None) -> None:
        self.chain = chain
        if not self._static:
            self._static_scene()
        p = self.plotter
        for bid in chain.moving_bodies() + [chain.base]:
            b = chain.bodies[bid]
            vis = b.visual
            if vis.get("shape") == "cylinder" and np.linalg.norm(np.asarray(vis["p1"]) - np.asarray(vis["p0"])) > 1e-9:
                mesh = cylinder_between(vis["p0"], vis["p1"], float(vis.get("radius_m", 0.03)))
            else:
                mesh = pv.Sphere(radius=0.03)
            self.meshes[bid] = mesh
            self.actors[bid] = p.add_mesh(mesh, color=BODY_COLORS.get(bid, DEFAULT_COLOR), smooth_shading=True, name=f"body_{bid}", pickable=True)
            self.axis_actors[bid] = [p.add_mesh(pv.Arrow(start=(0, 0, 0), direction=d, scale=0.12, tip_radius=0.08, shaft_radius=0.03), color=c,
                                                name=f"lax_{bid}_{nm}", pickable=False) for nm, d, c in AXIS_COLORS]
            self.com_actors[bid] = p.add_mesh(pv.Sphere(radius=0.015, center=b.com), color="#ff4fd8", name=f"com_{bid}", pickable=False)
            self.n_actor_creations += 5
        for j in chain.joints:
            self.joint_actors[j.name] = p.add_mesh(pv.Sphere(radius=0.026), color="#E8EDF5", name=f"joint_{j.name}", pickable=False)
        self.total_com_actor = p.add_mesh(pv.Sphere(radius=0.02), color="#ffd24f", name="com_total", pickable=False)
        self.set_visibility()
        self.update(chain.q if q is None else q)
        self.camera("isometrica")

    # ---- atualização por quadro (só transformações) ----
    def update(self, q, render: bool = True) -> dict:
        ch = self.chain
        fk = ch.forward_kinematics(q)
        self.q = np.asarray(q, float)
        for bid, act in self.actors.items():
            M = fk.T[bid]
            act.user_matrix = M
            for a in self.axis_actors[bid]:
                a.user_matrix = M
            self.com_actors[bid].user_matrix = M
        for j in ch.joints:
            self.joint_actors[j.name].user_matrix = T.make(None, fk.T[j.child][:3, 3])
        self.total_com_actor.user_matrix = T.make(None, ch.total_com(q))
        if render:
            self.plotter.render()
        return {"fk": fk}

    def body_world_matrix(self, bid: str) -> np.ndarray:
        return np.array(self.actors[bid].user_matrix.copy() if hasattr(self.actors[bid].user_matrix, "copy") else self.actors[bid].user_matrix)

    def set_visibility(self, axes: bool | None = None, com: bool | None = None) -> None:
        self.show_axes = self.show_axes if axes is None else axes
        self.show_com = self.show_com if com is None else com
        for bid in self.actors:
            for a in self.axis_actors[bid]:
                a.SetVisibility(self.show_axes)
            self.com_actors[bid].SetVisibility(self.show_com)
        self.total_com_actor.SetVisibility(self.show_com)

    # ---- vetores, trajetória ----
    def set_vectors(self, vectors: list, name: str = "vec") -> int:
        """vectors: [(origem_mundo, vetor_mundo, escala_m_por_unidade, cor), ...]. Reutiliza atores por nome. Retorna nº desenhado."""
        drawn = 0
        for i, (o, v, sc, color) in enumerate(vectors):
            arrow = vector_arrow(o, v, sc)
            nm = f"{name}_{i}"
            if arrow is None:
                self.plotter.remove_actor(nm, render=False)
                continue
            self.plotter.add_mesh(arrow, color=color, name=nm, pickable=False)
            drawn += 1
        return drawn

    def set_trajectory(self, points, color: str = "#3dd68c") -> None:
        pts = np.asarray(points, float)
        if len(pts) >= 2:
            self.plotter.add_mesh(pv.lines_from_points(pts), color=color, line_width=3, name="trajectory", pickable=False)

    def clear_trajectory(self) -> None:
        self.plotter.remove_actor("trajectory", render=False)

    # ---- seleção e câmera ----
    def select(self, bid: str | None) -> None:
        for name, act in self.actors.items():
            act.prop.color = SELECT_COLOR if name == bid else BODY_COLORS.get(name, DEFAULT_COLOR)
        self.selected = bid
        self.plotter.render()

    def body_for_actor(self, actor) -> str | None:
        for name, act in self.actors.items():
            if act is actor:
                return name
        return None

    def camera(self, preset: str) -> None:
        if preset not in CAMERA_PRESETS:
            raise KeyError(f"preset de câmera desconhecido: {preset}")
        self.plotter.camera_position = [CAMERA_PRESETS[preset][0], CAMERA_PRESETS[preset][1], CAMERA_PRESETS[preset][2]]
        self.plotter.render()

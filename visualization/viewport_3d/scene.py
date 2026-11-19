"""Cena 3D do membro inferior (PyVista/VTK). Independente de Qt: recebe qualquer plotter."""
from __future__ import annotations

import numpy as np
import pyvista as pv

from biomechanics.human_model.lower_limb import LowerLimbModel

COLORS = {"pelvis": "#8892a6", "femur": "#2389FF", "tibia": "#19C7D9", "fibula": "#7fdde6", "foot": "#E8EDF5"}
SELECT_COLOR = "#F5A623"


def cylinder_between(p0, p1, radius: float) -> pv.PolyData:
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    d = p1 - p0
    h = float(np.linalg.norm(d))
    if h < 1e-9:
        raise ValueError("segmento com comprimento nulo")
    return pv.Cylinder(center=(p0 + p1) / 2, direction=d / h, radius=radius, height=h, resolution=28)


def mesh_polydata(vertices, faces) -> pv.PolyData:
    """PolyData a partir de vértices (V,3) e faces triangulares (F,3)."""
    v = np.asarray(vertices, float)
    f = np.asarray(faces, np.int64)
    cells = np.hstack([np.full((len(f), 1), 3, np.int64), f]).ravel()
    return pv.PolyData(v, cells)


class LimbScene:
    def __init__(self, plotter) -> None:
        self.plotter = plotter
        self.model: LowerLimbModel | None = None
        self.actors: dict[str, object] = {}
        self.meshes: dict[str, pv.PolyData] = {}
        self.selected: str | None = None
        self._static = False

    def _build_static(self) -> None:
        p = self.plotter
        p.set_background("#10141C")
        grid = pv.Plane(center=(0.15, 0, 0), direction=(0, 1, 0), i_size=1.4, j_size=1.4, i_resolution=14, j_resolution=14)
        p.add_mesh(grid, style="wireframe", color="#2a3548", line_width=1, name="ground")
        for axis, color in (((1, 0, 0), "#ff5c6c"), ((0, 1, 0), "#3dd68c"), ((0, 0, 1), "#2389ff")):
            p.add_mesh(pv.Arrow(start=(0, 0, 0), direction=axis, scale=0.25, tip_radius=0.05, shaft_radius=0.02),
                       color=color, name=f"axis_{color}")
        p.add_axes(color="white")
        self._static = True

    def set_model(self, model: LowerLimbModel) -> None:
        self.model = model
        if not self._static:
            self._build_static()
        self.update(reset_camera=True)

    def update(self, reset_camera: bool = False) -> None:
        if self.model is None:
            return
        m, p = self.model, self.plotter
        ep = m.segment_endpoints()
        for name, (a, b) in ep.items():
            mesh = cylinder_between(a, b, m.segments[name].radius_m)
            color = SELECT_COLOR if name == self.selected else COLORS[name]
            if name in self.meshes:
                self.meshes[name].copy_from(mesh)
                self.actors[name].prop.color = color
            else:
                self.meshes[name] = mesh
                self.actors[name] = p.add_mesh(mesh, color=color, smooth_shading=True, name=f"seg_{name}", pickable=True)
        fk = m.forward_kinematics()
        for j in ("hip", "knee", "ankle"):
            p.add_mesh(pv.Sphere(radius=0.032, center=fk[j]), color="#E8EDF5", name=f"joint_{j}", pickable=False)
        com = m.total_com()
        p.add_mesh(pv.Sphere(radius=0.022, center=com), color="#ff4fd8", name="com", pickable=False)
        p.add_mesh(pv.Line(com, (com[0], 0.0, com[2])), color="#ff4fd8", line_width=2, name="com_line", pickable=False)
        if reset_camera:
            p.camera_position = [(2.2, 1.0, 2.6), (0.1, 0.5, 0.0), (0, 1, 0)]
        p.render()

    def show_mesh(self, vertices, faces) -> None:
        """Mostra a malha importada (em metros), substituindo a anterior; reajusta a câmera aos limites dela."""
        if not self._static:
            self._build_static()
        mesh = mesh_polydata(vertices, faces)
        self.plotter.add_mesh(mesh, color="#9fb3cc", smooth_shading=False, show_edges=False, name="imported_mesh", pickable=False)
        self.plotter.reset_camera()
        self.plotter.render()

    def clear_mesh(self) -> None:
        self.plotter.remove_actor("imported_mesh")

    def select(self, name: str | None) -> None:
        self.selected = name if name in COLORS else None
        self.update()

    def name_for_actor(self, actor) -> str | None:
        for n, a in self.actors.items():
            if a is actor:
                return n
        return None

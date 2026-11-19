"""Viewport 3D (pyvistaqt). Se o contexto OpenGL/VTK não estiver disponível, mostra o motivo (sem simular 3D)."""
from __future__ import annotations

import logging
import os

from PySide6.QtCore import Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from biomechanics.human_model.lower_limb import LowerLimbModel

log = logging.getLogger("nexus.viewport")


class Viewport3D(QWidget):
    segment_picked = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.available = False
        self.scene = None
        self.plotter = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        reason = self._try_init(lay)
        if not self.available:
            lbl = QLabel(f"Viewport 3D indisponível: {reason}")
            lbl.setWordWrap(True)
            lbl.setObjectName("planned")
            lay.addWidget(lbl)
            log.warning("Viewport 3D indisponível: %s", reason)

    def _try_init(self, lay) -> str:
        platform = QGuiApplication.platformName()
        if os.environ.get("NEXUS_DISABLE_3D") == "1" or platform in ("offscreen", "minimal"):
            return f"plataforma gráfica '{platform}' sem contexto OpenGL (use o app normal no Windows)"
        try:
            from pyvistaqt import QtInteractor
            from visualization.viewport_3d.scene import LimbScene
            self.plotter = QtInteractor(self)
            lay.addWidget(self.plotter.interactor)
            self.scene = LimbScene(self.plotter)
            try:  # seleção de componentes por clique
                self.plotter.enable_mesh_picking(self._on_pick, use_actor=True, left_clicking=True,
                                                 show=False, show_message=False)
            except Exception as exc:  # recurso opcional
                log.warning("Seleção por clique indisponível: %s", exc)
            self.available = True
            return ""
        except Exception as exc:
            return f"{type(exc).__name__}: {exc}"

    def _on_pick(self, actor) -> None:
        name = self.scene.name_for_actor(actor) if self.scene else None
        if name:
            self.segment_picked.emit(name)

    def _reset_plotter(self) -> None:
        """Troca de tipo de cena: limpa o plotter e descarta cenas anteriores (cada cena recria só o que usa)."""
        from visualization.viewport_3d.scene import LimbScene
        self.plotter.clear()
        self.spatial_scene = None
        self.scene = LimbScene(self.plotter)

    def set_model(self, model: LowerLimbModel | None) -> None:
        if self.available and model is not None:
            if getattr(self, "spatial_scene", None) is not None:
                self._reset_plotter()
            self.scene.set_model(model)

    # ---- cena espacial dinâmica (BIO-003) ----
    spatial_scene = None

    def set_spatial_chain(self, chain, q=None) -> bool:
        if not self.available:
            return False
        from visualization.viewport_3d.spatial_scene import SpatialScene
        self.plotter.clear()
        self.scene.meshes.clear()
        self.scene.actors.clear()
        self.scene._static = False
        self.spatial_scene = SpatialScene(self.plotter)
        self.spatial_scene.set_chain(chain, q)
        return True

    def show_spatial_frame(self, q) -> None:
        if self.available and self.spatial_scene is not None:
            self.spatial_scene.update(q)

    def spatial_camera(self, preset: str) -> None:
        if self.available and self.spatial_scene is not None:
            self.spatial_scene.camera(preset)

    def spatial_visibility(self, axes: bool, com: bool) -> None:
        if self.available and self.spatial_scene is not None:
            self.spatial_scene.set_visibility(axes, com)
            self.plotter.render()

    def show_mesh(self, vertices, faces) -> bool:
        if not self.available:
            return False
        if getattr(self, "spatial_scene", None) is not None:
            self._reset_plotter()
        self.scene.show_mesh(vertices, faces)
        return True

    def refresh(self) -> None:
        if self.available:
            self.scene.update()

    def select(self, name: str | None) -> None:
        if self.available:
            self.scene.select(name)

    def closeEvent(self, e) -> None:
        if self.plotter is not None:
            self.plotter.close()
        super().closeEvent(e)

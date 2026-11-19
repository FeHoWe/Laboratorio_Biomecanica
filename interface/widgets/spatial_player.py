"""Barra de reprodução da simulação espacial: play/pause/reiniciar, velocidade, posição, câmera, eixos e CM.
Só escolhe quadros de uma Trajectory já calculada (nada é inventado)."""
from __future__ import annotations

import time

import numpy as np
from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QLabel, QPushButton, QSlider, QWidget

from visualization.viewport_3d.playback import SPEEDS, PlaybackController
from visualization.viewport_3d.spatial_scene import CAMERA_PRESETS


class SpatialPlayer(QWidget):
    frame_changed = Signal(int)
    camera_requested = Signal(str)
    visibility_changed = Signal(bool, bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.ctrl: PlaybackController | None = None
        self._last = 0.0
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)
        self.btn_play = QPushButton("▶ Reproduzir")
        self.btn_restart = QPushButton("⏮ Reiniciar")
        self.speed = QComboBox()
        for s in SPEEDS:
            self.speed.addItem(f"{s:g}×", s)
        self.speed.setCurrentIndex(SPEEDS.index(1.0))
        self.slider = QSlider()
        self.slider.setOrientation(__import__("PySide6.QtCore", fromlist=["Qt"]).Qt.Horizontal)
        self.label = QLabel("t = — s")
        self.camera = QComboBox()
        self.camera.addItems(list(CAMERA_PRESETS))
        self.axes = QCheckBox("Eixos locais")
        self.axes.setChecked(True)
        self.com = QCheckBox("CM")
        self.com.setChecked(True)
        lay = QHBoxLayout(self)
        for w in (self.btn_play, self.btn_restart, QLabel("Vel."), self.speed, self.slider, self.label, QLabel("Câmera"), self.camera, self.axes, self.com):
            lay.addWidget(w)
        self.btn_play.clicked.connect(self.toggle)
        self.btn_restart.clicked.connect(self.restart)
        self.speed.currentIndexChanged.connect(lambda _: self.ctrl and self.ctrl.set_speed(self.speed.currentData()))
        self.slider.valueChanged.connect(self._slider)
        self.camera.currentTextChanged.connect(self.camera_requested.emit)
        self.axes.toggled.connect(lambda _: self.visibility_changed.emit(self.axes.isChecked(), self.com.isChecked()))
        self.com.toggled.connect(lambda _: self.visibility_changed.emit(self.axes.isChecked(), self.com.isChecked()))
        self.setEnabled(False)

    def set_time(self, t) -> None:
        self.timer.stop()
        self.ctrl = PlaybackController(np.asarray(t, float))
        self.ctrl.set_speed(self.speed.currentData())
        self.slider.blockSignals(True)
        self.slider.setRange(0, len(self.ctrl.t) - 1)
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        self.btn_play.setText("▶ Reproduzir")
        self.setEnabled(True)
        self._emit()

    def toggle(self) -> None:
        if self.ctrl is None:
            return
        if self.ctrl.playing:
            self.ctrl.pause()
            self.timer.stop()
            self.btn_play.setText("▶ Reproduzir")
        else:
            self.ctrl.play()
            self._last = time.perf_counter()
            self.timer.start()
            self.btn_play.setText("⏸ Pausar")

    def restart(self) -> None:
        if self.ctrl:
            self.ctrl.restart()
            self._emit()

    def _tick(self) -> None:
        now = time.perf_counter()
        self.ctrl.advance(now - self._last)
        self._last = now
        self._emit()
        if not self.ctrl.playing:
            self.timer.stop()
            self.btn_play.setText("▶ Reproduzir")

    def _slider(self, v: int) -> None:
        if self.ctrl:
            self.ctrl.seek(float(self.ctrl.t[v]))
            self._emit(update_slider=False)

    def _emit(self, update_slider: bool = True) -> None:
        i = self.ctrl.index
        if update_slider:
            self.slider.blockSignals(True)
            self.slider.setValue(i)
            self.slider.blockSignals(False)
        self.label.setText(f"t = {self.ctrl.time:.3f} s")
        self.frame_changed.emit(i)

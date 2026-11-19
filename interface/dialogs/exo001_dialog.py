"""Diálogo de parâmetros do EXO-001 (assistência articular por exoesqueleto)."""
from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel, QSpinBox,
                               QVBoxLayout)

from exoskeleton.actuators.actuator import Actuator
from exoskeleton.analysis.assist import MODES, Exo001Params, ExoConfig, default_params


def _sb(lo, hi, step, dec, val):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setSingleStep(step)
    s.setDecimals(dec)
    s.setValue(val)
    return s


class Exo001Dialog(QDialog):
    def __init__(self, params: Exo001Params | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("EXO-001 — Assistência articular por exoesqueleto")
        self.p = params or default_params()
        e = self.p.exo
        warn = QLabel("Parâmetros DEMONSTRATIVOS (hipotéticos); não representam produto real nem dispositivo médico. "
                      "Modelo humano: cadeia de 3 segmentos (BIO-002, modelo A).")
        warn.setObjectName("planned")
        warn.setWordWrap(True)
        self.joint = QComboBox()
        for i, n in enumerate(self.p.model.joint_names):
            self.joint.addItem(f"{i + 1}: {n}")
        self.joint.setCurrentIndex(e.joint_index)
        self.mode = QComboBox()
        self.mode.addItems(MODES)
        self.mode.setCurrentText(e.mode)
        self.gain = _sb(0, 5, 0.05, 2, e.gain)
        self.masses = [_sb(0, 50, 0.1, 2, m) for m in e.added_masses_kg]
        a = e.actuator
        self.tau = _sb(0.1, 2000, 1, 1, a.tau_stall_nm)
        self.w0 = _sb(0.1, 500, 0.5, 2, a.omega_noload_rad_s)
        self.eff = _sb(0.05, 1, 0.05, 2, a.efficiency)
        self.dur = _sb(0.05, 60, 0.1, 3, self.p.duration_s)
        self.n = QSpinBox()
        self.n.setRange(5, 5001)
        self.n.setValue(self.p.samples)
        f = QFormLayout()
        f.addRow("Junta assistida", self.joint)
        f.addRow("Modo", self.mode)
        f.addRow("Ganho (fração)", self.gain)
        for i, s in enumerate(self.masses):
            f.addRow(f"Massa adicionada seg. {i + 1} (kg)", s)
        f.addRow("τ de bloqueio (N·m)", self.tau)
        f.addRow("ω sem carga (rad/s)", self.w0)
        f.addRow("Eficiência η", self.eff)
        f.addRow("Duração (s)", self.dur)
        f.addRow("Amostras", self.n)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(warn)
        lay.addLayout(f)
        lay.addWidget(bb)

    def params(self) -> Exo001Params:
        cfg = ExoConfig(joint_index=self.joint.currentIndex(), mode=self.mode.currentText(), gain=self.gain.value(),
                        added_masses_kg=[s.value() for s in self.masses],
                        actuator=Actuator(self.tau.value(), self.w0.value(), self.eff.value(), self.p.exo.actuator.mass_kg))
        return Exo001Params(self.p.model, cfg, self.dur.value(), self.n.value())

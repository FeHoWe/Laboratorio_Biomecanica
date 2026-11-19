"""Diálogo de parâmetros da SIM-001 (dinâmica passiva)."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel, QVBoxLayout

from research.experiments.passive_sim import PassiveParams

FIELDS = [("l1", "L1 (m)", 0.01, 3, 0.01, 3), ("m1", "m1 (kg)", 0.01, 500, 0.1, 3), ("com1", "CM1 (fração)", 0, 1, 0.01, 2),
          ("l2", "L2 (m)", 0.01, 3, 0.01, 3), ("m2", "m2 (kg)", 0.01, 500, 0.1, 3), ("com2", "CM2 (fração)", 0, 1, 0.01, 2),
          ("q1_deg", "q1 inicial (°, abs.; −90 = pendurado)", -360, 360, 1, 1), ("q2_deg", "q2 inicial (°, rel.)", -360, 360, 1, 1),
          ("qd1_deg_s", "q̇1 inicial (°/s)", -3600, 3600, 5, 1), ("qd2_deg_s", "q̇2 inicial (°/s)", -3600, 3600, 5, 1),
          ("t_end_s", "Duração (s)", 0.01, 600, 0.5, 2), ("dt_s", "Passo dt (s)", 0.0001, 0.01, 0.0005, 4)]


class PassiveDialog(QDialog):
    def __init__(self, params: PassiveParams | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("SIM-001 — Dinâmica passiva (sem torques, sem atrito)")
        self.base = params or PassiveParams()
        warn = QLabel("Parâmetros padrão DEMONSTRATIVOS. A energia mecânica deve se conservar (deriva reportada).")
        warn.setObjectName("planned")
        warn.setWordWrap(True)
        self.spins = {}
        form = QFormLayout()
        for attr, label, lo, hi, step, dec in FIELDS:
            sb = QDoubleSpinBox()
            sb.setRange(lo, hi)
            sb.setDecimals(dec)
            sb.setSingleStep(step)
            sb.setValue(getattr(self.base, attr))
            self.spins[attr] = sb
            form.addRow(label, sb)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(warn)
        lay.addLayout(form)
        lay.addWidget(bb)

    def params(self) -> PassiveParams:
        from dataclasses import replace
        return replace(self.base, **{k: s.value() for k, s in self.spins.items()})

"""Diálogo de parâmetros do BIO-001."""
from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout,
                               QLabel, QSpinBox, QVBoxLayout)

from research.experiments.bio001 import Bio001Params, ModelConfig, default_params

FIELDS = [  # (atributo, rótulo, mín, máx, passo, decimais)
    ("l1", "L1 (m)", 0.01, 3.0, 0.01, 3), ("m1", "m1 (kg)", 0.01, 500, 0.1, 3), ("com1", "CM1 (fração de L1)", 0, 1, 0.01, 2),
    ("l2", "L2 (m)", 0.01, 3.0, 0.01, 3), ("m2", "m2 (kg)", 0.01, 500, 0.1, 3), ("com2", "CM2 (fração de L2)", 0, 1, 0.01, 2),
    ("q1_start_deg", "q1 inicial (°, abs.)", -360, 360, 1, 1), ("q1_end_deg", "q1 final (°)", -360, 360, 1, 1),
    ("q2_start_deg", "q2 inicial (°, rel.)", -360, 360, 1, 1), ("q2_end_deg", "q2 final (°)", -360, 360, 1, 1),
]


class _ModelBox(QGroupBox):
    def __init__(self, cfg: ModelConfig) -> None:
        super().__init__(cfg.name)
        self.cfg = cfg
        self.spins: dict[str, QDoubleSpinBox] = {}
        form = QFormLayout(self)
        for attr, label, lo, hi, step, dec in FIELDS + [("fx", "Força na ponta Fx (N)", -5000, 5000, 1, 1),
                                                        ("fy", "Força na ponta Fy (N)", -5000, 5000, 1, 1)]:
            sb = QDoubleSpinBox()
            sb.setRange(lo, hi)
            sb.setSingleStep(step)
            sb.setDecimals(dec)
            sb.setValue(getattr(cfg, attr) if hasattr(cfg, attr) else cfg.tip_force_n[0 if attr == "fx" else 1])
            self.spins[attr] = sb
            form.addRow(label, sb)

    def config(self) -> ModelConfig:
        v = {k: s.value() for k, s in self.spins.items()}
        fx, fy = v.pop("fx"), v.pop("fy")
        return replace(self.cfg, tip_force_n=(fx, fy), **v)


class Bio001Dialog(QDialog):
    def __init__(self, params: Bio001Params | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("BIO-001 — Comparative Joint Mechanics")
        params = params or default_params()
        warn = QLabel("Parâmetros padrão são DEMONSTRATIVOS (hipotéticos). Não representam anatomia real.")
        warn.setObjectName("planned")
        self.box_a, self.box_b = _ModelBox(params.model_a), _ModelBox(params.model_b)
        self.dur = QDoubleSpinBox()
        self.dur.setRange(0.05, 60)
        self.dur.setDecimals(3)
        self.dur.setValue(params.duration_s)
        self.n = QSpinBox()
        self.n.setRange(5, 20001)
        self.n.setValue(params.samples)
        top = QFormLayout()
        top.addRow("Duração (s)", self.dur)
        top.addRow("Amostras", self.n)
        row = QHBoxLayout()
        row.addWidget(self.box_a)
        row.addWidget(self.box_b)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        lay.addWidget(warn)
        lay.addLayout(top)
        lay.addLayout(row)
        lay.addWidget(bb)

    def params(self) -> Bio001Params:
        return Bio001Params(self.box_a.config(), self.box_b.config(), self.dur.value(), self.n.value())

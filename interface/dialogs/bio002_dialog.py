"""Diálogo de parâmetros do BIO-002 (cadeias de 3 segmentos)."""
from __future__ import annotations

from dataclasses import replace

from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QDoubleSpinBox, QGridLayout, QGroupBox, QHBoxLayout,
                               QLabel, QSpinBox, QVBoxLayout, QFormLayout)

from research.experiments.bio002 import Bio002Params, ChainModel, default_params


def _sb(lo, hi, step, dec, val):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setSingleStep(step)
    s.setDecimals(dec)
    s.setValue(val)
    return s


class _ChainBox(QGroupBox):
    def __init__(self, cfg: ChainModel) -> None:
        super().__init__(cfg.name)
        self.cfg = cfg
        n = len(cfg.lengths_m)
        g = QGridLayout(self)
        for c, h in enumerate(["Junta", "L (m)", "m (kg)", "CM (fr.)", "q ini (°)", "q fim (°)"]):
            g.addWidget(QLabel(h), 0, c)
        self.rows = []
        for i in range(n):
            w = (_sb(0.01, 3, 0.01, 3, cfg.lengths_m[i]), _sb(0.01, 500, 0.1, 3, cfg.masses_kg[i]),
                 _sb(0, 1, 0.01, 2, cfg.com_fracs[i]), _sb(-360, 360, 1, 1, cfg.q_start_deg[i]),
                 _sb(-360, 360, 1, 1, cfg.q_end_deg[i]))
            g.addWidget(QLabel(f"{i+1}: {cfg.joint_names[i]}"), i + 1, 0)
            for c, x in enumerate(w, 1):
                g.addWidget(x, i + 1, c)
            self.rows.append(w)
        self.fx, self.fy = _sb(-5000, 5000, 1, 1, cfg.tip_force_n[0]), _sb(-5000, 5000, 1, 1, cfg.tip_force_n[1])
        g.addWidget(QLabel("Fx ponta (N)"), n + 1, 0)
        g.addWidget(self.fx, n + 1, 1)
        g.addWidget(QLabel("Fy ponta (N)"), n + 1, 2)
        g.addWidget(self.fy, n + 1, 3)

    def config(self) -> ChainModel:
        col = lambda k: [r[k].value() for r in self.rows]
        return replace(self.cfg, lengths_m=col(0), masses_kg=col(1), com_fracs=col(2), q_start_deg=col(3),
                       q_end_deg=col(4), tip_force_n=(self.fx.value(), self.fy.value()))


class Bio002Dialog(QDialog):
    def __init__(self, params: Bio002Params | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("BIO-002 — Comparative Joint Mechanics (3 segmentos)")
        params = params or default_params()
        warn = QLabel("Parâmetros padrão DEMONSTRATIVOS (hipotéticos). q1 absoluto; q2, q3 relativos ao segmento anterior.")
        warn.setObjectName("planned")
        warn.setWordWrap(True)
        self.a, self.b = _ChainBox(params.model_a), _ChainBox(params.model_b)
        self.dur = _sb(0.05, 60, 0.1, 3, params.duration_s)
        self.n = QSpinBox()
        self.n.setRange(5, 5001)
        self.n.setValue(params.samples)
        top = QFormLayout()
        top.addRow("Duração (s)", self.dur)
        top.addRow("Amostras", self.n)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay = QVBoxLayout(self)
        for w in (warn,):
            lay.addWidget(w)
        lay.addLayout(top)
        lay.addWidget(self.a)
        lay.addWidget(self.b)
        lay.addWidget(bb)

    def params(self) -> Bio002Params:
        return Bio002Params(self.a.config(), self.b.config(), self.dur.value(), self.n.value())

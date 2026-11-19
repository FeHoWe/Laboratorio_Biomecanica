"""Diálogo de parâmetros do BIO-003 (dinâmica espacial do membro inferior)."""
from __future__ import annotations

from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox, QFormLayout, QLabel, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from biomechanics.human_model.spatial_lower_limb import DOF_NAMES
from research.experiments.bio003 import SEGMENTS, Bio003Error, Bio003Params, default_params

DOF_COLS = ["mín (°)", "máx (°)", "q0 (°)", "q̇0 (°/s)", "τ const (N·m)", "τ amp (N·m)", "f (Hz)"]
SEG_COLS = ["comprimento (m)", "massa (kg)", "CM (fração de L)"]


def _sb(lo, hi, dec, val, step=0.1):
    s = QDoubleSpinBox()
    s.setRange(lo, hi)
    s.setDecimals(dec)
    s.setSingleStep(step)
    s.setValue(val)
    return s


def _table(rows, cols, row_names, col_names, data):
    t = QTableWidget(rows, cols)
    t.setVerticalHeaderLabels(row_names)
    t.setHorizontalHeaderLabels(col_names)
    for i, r in enumerate(data):
        for j, v in enumerate(r):
            t.setItem(i, j, QTableWidgetItem(f"{v:g}"))
    t.resizeColumnsToContents()
    t.setMinimumHeight(30 * (rows + 2))
    return t


class Bio003Dialog(QDialog):
    def __init__(self, params: Bio003Params | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("BIO-003 — Dinâmica espacial do membro inferior")
        self.setMinimumWidth(760)
        p = params or default_params()
        warn = QLabel("Parâmetros DEMONSTRATIVOS (hipotéticos), sem fonte científica verificada. Quadril = 3 DOFs rotacionais, joelho = 1, "
                      "tornozelo = 2 (simplificações mecânicas). Limites articulares são apenas reportados, não impostos. Não é dispositivo médico.")
        warn.setObjectName("planned")
        warn.setWordWrap(True)
        self.seg = _table(3, 3, list(SEGMENTS), SEG_COLS, [[p.segments[k]["length_m"], p.segments[k]["mass_kg"], p.segments[k]["com_frac"]] for k in SEGMENTS])
        rows = [[p.limits_deg[k][0], p.limits_deg[k][1], p.q0_deg[k], p.qd0_deg_s[k], p.tau_const_nm[k], p.tau_amp_nm[k], p.tau_freq_hz[k]] for k in range(6)]
        self.dof = _table(6, 7, DOF_NAMES, DOF_COLS, rows)
        self.g = [_sb(-100, 100, 4, v, 0.1) for v in p.gravity_m_s2]
        self.dur = _sb(0.01, 600, 3, p.duration_s)
        self.dt = _sb(0.00001, 1, 5, p.dt_s, 0.0005)
        self.method = QComboBox()
        self.method.addItems(["rk4", "adaptive"])
        self.method.setCurrentText(p.method)
        self._source = p.source
        f = QFormLayout()
        f.addRow("Gravidade x/y/z (m/s²)", self._row(self.g))
        f.addRow("Duração (s)", self.dur)
        f.addRow("Passo (s)", self.dt)
        f.addRow("Integrador", self.method)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)
        self.error = QLabel("")
        self.error.setStyleSheet("color:#ff5c6c")
        self.error.setWordWrap(True)
        lay = QVBoxLayout(self)
        for w in (warn, QLabel("Segmentos"), self.seg, QLabel("Graus de liberdade: limites, pose inicial, velocidades, torques"), self.dof):
            lay.addWidget(w)
        lay.addLayout(f)
        lay.addWidget(self.error)
        lay.addWidget(bb)

    @staticmethod
    def _row(widgets):
        from PySide6.QtWidgets import QHBoxLayout, QWidget
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        for x in widgets:
            h.addWidget(x)
        return w

    @staticmethod
    def _num(t: QTableWidget, r: int, c: int) -> float:
        item = t.item(r, c)
        try:
            return float(item.text().replace(",", "."))
        except (AttributeError, ValueError) as exc:
            raise Bio003Error(f"Valor inválido na tabela (linha {r + 1}, coluna {c + 1})") from exc

    def params(self) -> Bio003Params:
        n = self._num
        segs = {k: {"length_m": n(self.seg, i, 0), "mass_kg": n(self.seg, i, 1), "com_frac": n(self.seg, i, 2)} for i, k in enumerate(SEGMENTS)}
        d = self.dof
        p = Bio003Params(segs, [[n(d, k, 0), n(d, k, 1)] for k in range(6)], [n(d, k, 2) for k in range(6)], [n(d, k, 3) for k in range(6)],
                         tuple(s.value() for s in self.g), [n(d, k, 4) for k in range(6)], [n(d, k, 5) for k in range(6)], [n(d, k, 6) for k in range(6)],
                         self.dur.value(), self.dt.value(), self.method.currentText(), self._source)
        p.validate()
        return p

    def _accept(self) -> None:
        try:
            self.params()
        except Bio003Error as exc:
            self.error.setText(str(exc))
            return
        self.accept()

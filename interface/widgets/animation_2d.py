"""Animação 2D dos dois modelos, dirigida pelos resultados calculados (não por movimento aleatório)."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

from interface import theme


class _Canvas(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.result: dict | None = None
        self.frame = 0
        self.setMinimumSize(300, 240)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor(theme.BG))
        if not self.result:
            p.setPen(QColor(theme.TEXT2))
            p.drawText(self.rect(), Qt.AlignCenter, "Execute um experimento BIO-001 (menu Pesquisa)")
            return
        keys = [k for k in ("A", "B") if k in self.result]
        reach = max(self.result[k]["summary"]["total_length_m"] for k in keys)
        scale = min(self.width() / (4.6 * reach), self.height() / (2.4 * reach))
        base_y = self.height() * 0.12
        offsets = {"A": -1.2 * reach, "B": 1.2 * reach} if len(keys) == 2 else {"A": 0.0}
        for key, color, ox in [(k, {"A": theme.BLUE, "B": theme.CYAN}[k], offsets[k]) for k in keys]:
            r = self.result[key]
            def P(xy, ox=ox):
                return QPointF(self.width() / 2 + (xy[0] + ox) * scale, base_y + (-xy[1]) * scale)
            # trilha da ponta até o quadro atual
            p.setPen(QPen(QColor(theme.TEXT2), 1, Qt.DotLine))
            pts = [P(r["tip_xy"][i]) for i in range(0, self.frame + 1, 2)]
            for a, b in zip(pts[:-1], pts[1:]):
                p.drawLine(a, b)
            o, j, t = P((0, 0)), P(r["joint_xy"][self.frame]), P(r["tip_xy"][self.frame])
            p.setPen(QPen(QColor(color), 5, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(o, j)
            p.drawLine(j, t)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme.TEXT))
            for pt in (o, j, t):
                p.drawEllipse(pt, 4, 4)
            p.setPen(QColor(color))
            p.drawText(int(P((0, 0)).x()) - 90, int(self.height() - 12), r["name"][:34])


class Animation2D(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.canvas = _Canvas()
        self.play_btn = QPushButton("▶ Reproduzir")
        self.slider = QSlider(Qt.Horizontal)
        self.label = QLabel("t = — s")
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.play_btn.clicked.connect(self.toggle)
        self.slider.valueChanged.connect(self.set_frame)
        row = QHBoxLayout()
        for w in (self.play_btn, self.slider, self.label):
            row.addWidget(w)
        lay = QVBoxLayout(self)
        lay.addWidget(self.canvas, 1)
        lay.addLayout(row)
        self.setEnabled(False)

    def set_result(self, result: dict) -> None:
        self.timer.stop()
        self.canvas.result = result
        n = len(result["A"]["t"])
        T = float(result["A"]["t"][-1])
        self.timer.setInterval(max(5, int(T * 1000 / (n - 1))))
        self.slider.blockSignals(True)
        self.slider.setRange(0, n - 1)
        self.slider.setValue(0)
        self.slider.blockSignals(False)
        self.setEnabled(True)
        self.set_frame(0)

    def set_frame(self, i: int) -> None:
        if not self.canvas.result:
            return
        self.canvas.frame = int(i)
        self.label.setText(f"t = {self.canvas.result['A']['t'][i]:.3f} s")
        self.canvas.update()

    def toggle(self) -> None:
        if self.timer.isActive():
            self.timer.stop()
            self.play_btn.setText("▶ Reproduzir")
        else:
            if self.slider.value() >= self.slider.maximum():
                self.slider.setValue(0)
            self.timer.start()
            self.play_btn.setText("⏸ Pausar")

    def _tick(self) -> None:
        if self.slider.value() >= self.slider.maximum():
            self.toggle()
        else:
            self.slider.setValue(self.slider.value() + 1)

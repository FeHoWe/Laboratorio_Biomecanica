"""Área central reservada ao viewport 3D (Fase 2). Não é uma simulação nem um 3D falso."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from interface import theme


class ViewportPlaceholder(QWidget):
    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(theme.BG))
        p.setPen(QPen(QColor(theme.PANEL2), 1))
        for x in range(0, self.width(), 40):
            p.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), 40):
            p.drawLine(0, y, self.width(), y)
        p.setPen(QColor(theme.CYAN))
        p.drawText(self.rect(), Qt.AlignCenter,
                   "Viewport 3D — PLANEJADO (Fase 2)\nVTK/PyVista ainda não integrados")

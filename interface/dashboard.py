"""Tela inicial (sem projeto aberto)."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget

from application.version import APP_NAME, PHASE, __version__


class Dashboard(QWidget):
    new_requested = Signal()
    open_requested = Signal()
    recent_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        title = QLabel(APP_NAME)
        title.setObjectName("title")
        sub = QLabel(f"Computational Biomechanics Laboratory — v{__version__} ({PHASE})\n"
                     "Plataforma de pesquisa e aprendizado computacional. Não é dispositivo médico.")
        sub.setObjectName("subtitle")
        new_btn, open_btn = QPushButton("Novo projeto…"), QPushButton("Abrir projeto…")
        new_btn.clicked.connect(self.new_requested)
        open_btn.clicked.connect(self.open_requested)
        self.recent = QListWidget()
        self.recent.itemActivated.connect(lambda it: self.recent_requested.emit(it.text()))
        row = QHBoxLayout()
        row.addWidget(new_btn)
        row.addWidget(open_btn)
        row.addStretch(1)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 40, 40, 40)
        lay.addWidget(title)
        lay.addWidget(sub)
        lay.addSpacing(16)
        lay.addLayout(row)
        lay.addSpacing(16)
        lay.addWidget(QLabel("Projetos recentes (duplo clique para abrir)"))
        lay.addWidget(self.recent, 1)

    def set_recent(self, paths: list[str]) -> None:
        self.recent.clear()
        self.recent.addItems(paths)

"""Histórico de experimentos (índice SQLite): filtrar por tipo, ordenar por métrica."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                               QVBoxLayout)


class HistoryDialog(QDialog):
    open_requested = Signal(str)  # id do experimento

    def __init__(self, history, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Histórico de experimentos (SQLite)")
        self.resize(720, 420)
        self.history = history
        self.type_box = QComboBox()
        self.type_box.addItem("(todos os tipos)", None)
        for t in history.types():
            self.type_box.addItem(t, t)
        self.metric_box = QComboBox()
        self.order_box = QComboBox()
        self.order_box.addItems(["crescente", "decrescente"])
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Tipo", "Nome", "Criado (UTC)", "Métrica"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.count = QLabel()
        open_btn = QPushButton("Selecionar na árvore")
        open_btn.clicked.connect(self._open_current)
        self.table.cellDoubleClicked.connect(lambda *_: self._open_current())
        row = QHBoxLayout()
        for lbl, w in (("Tipo", self.type_box), ("Métrica", self.metric_box), ("Ordem", self.order_box)):
            row.addWidget(QLabel(lbl))
            row.addWidget(w, 1)
        lay = QVBoxLayout(self)
        lay.addLayout(row)
        lay.addWidget(self.table, 1)
        bot = QHBoxLayout()
        bot.addWidget(self.count, 1)
        bot.addWidget(open_btn)
        lay.addLayout(bot)
        self.type_box.currentIndexChanged.connect(self._reload_metrics)
        self.metric_box.currentIndexChanged.connect(self._fill)
        self.order_box.currentIndexChanged.connect(self._fill)
        self._reload_metrics()

    def _reload_metrics(self) -> None:
        self.metric_box.blockSignals(True)
        self.metric_box.clear()
        self.metric_box.addItem("(nenhuma)", None)
        for m in self.history.metric_names(self.type_box.currentData()):
            self.metric_box.addItem(m, m)
        self.metric_box.blockSignals(False)
        self._fill()

    def _fill(self) -> None:
        rows = self.history.list_experiments(self.type_box.currentData(), self.metric_box.currentData(),
                                             order_desc=self.order_box.currentIndex() == 1)
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            vals = [r["id"], r["type"], r["name"], r["created"], "—" if r["value"] is None else f"{r['value']:.6g}"]
            for c, v in enumerate(vals):
                self.table.setItem(i, c, QTableWidgetItem(v))
        self.count.setText(f"{len(rows)} experimento(s)")

    def _open_current(self) -> None:
        r = self.table.currentRow()
        if r >= 0:
            self.open_requested.emit(self.table.item(r, 0).text())

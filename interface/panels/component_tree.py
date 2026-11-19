"""Árvore de componentes do projeto (reflete apenas dados reais do projeto)."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem


class ComponentTree(QTreeWidget):
    selection_info = Signal(str, dict)  # (tipo, dados)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.currentItemChanged.connect(self._emit)

    def populate(self, data: dict | None) -> None:
        self.clear()
        if not data:
            return
        root = QTreeWidgetItem([data["name"]])
        root.setData(0, Qt.UserRole, ("project", data))
        for label, key in (("Modelos", "models"), ("Experimentos", "experiments")):
            group = QTreeWidgetItem([f"{label} ({len(data[key])})"])
            group.setData(0, Qt.UserRole, ("group", {"grupo": label, "itens": len(data[key])}))
            for item in data[key]:
                child = QTreeWidgetItem([item["name"]])
                child.setData(0, Qt.UserRole, (key[:-1], item))
                group.addChild(child)
            root.addChild(group)
        self.addTopLevelItem(root)
        self.expandAll()
        self.setCurrentItem(root)

    def _emit(self, current, _previous) -> None:
        if current is None:
            return
        kind, payload = current.data(0, Qt.UserRole)
        self.selection_info.emit(kind, payload)

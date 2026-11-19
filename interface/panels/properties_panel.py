"""Painel de propriedades. Para o projeto: nome e descrição editáveis."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QFormLayout, QLabel, QLineEdit, QPlainTextEdit,
                               QPushButton, QVBoxLayout, QWidget)


class PropertiesPanel(QWidget):
    apply_requested = Signal(str, str)  # nome, descrição

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.name_edit = QLineEdit()
        self.desc_edit = QPlainTextEdit()
        self.desc_edit.setMaximumHeight(90)
        self.readonly = QLabel()
        self.readonly.setWordWrap(True)
        self.apply_btn = QPushButton("Aplicar")
        self.apply_btn.clicked.connect(
            lambda: self.apply_requested.emit(self.name_edit.text(), self.desc_edit.toPlainText()))
        self.hint = QLabel("Nenhum item selecionado.")
        self.hint.setObjectName("subtitle")
        form = QFormLayout()
        form.addRow("Nome", self.name_edit)
        form.addRow("Descrição", self.desc_edit)
        self.form_widget = QWidget()
        self.form_widget.setLayout(form)
        lay = QVBoxLayout(self)
        lay.addWidget(self.hint)
        lay.addWidget(self.form_widget)
        lay.addWidget(self.apply_btn)
        lay.addWidget(self.readonly)
        lay.addStretch(1)
        self.clear()

    def clear(self) -> None:
        self.form_widget.hide()
        self.apply_btn.hide()
        self.readonly.setText("")
        self.hint.setText("Nenhum item selecionado.")
        self.hint.show()

    def show_item(self, kind: str, payload: dict) -> None:
        if kind == "project":
            self.hint.hide()
            self.form_widget.show()
            self.apply_btn.show()
            self.name_edit.setText(payload["name"])
            self.desc_edit.setPlainText(payload["description"])
            self.readonly.setText(
                f"ID: {payload['id']}\nCriado: {payload['created']}\n"
                f"Modificado: {payload['modified']}\nUnidades: {payload['settings'].get('units')}\n"
                f"Schema: v{payload['schema_version']}")
        else:
            self.form_widget.hide()
            self.apply_btn.hide()
            self.hint.show()
            self.hint.setText(f"Tipo: {kind}")
            self.readonly.setText("\n".join(f"{k}: {v}" for k, v in payload.items()))

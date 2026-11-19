"""Diálogo de novo projeto."""
from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
                               QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget)


def slugify(name: str) -> str:
    s = re.sub(r"[^\w\-]+", "_", name.strip(), flags=re.UNICODE).strip("_")
    return s or "projeto"


class NewProjectDialog(QDialog):
    def __init__(self, default_parent: Path | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Novo projeto")
        self.name = QLineEdit()
        self.desc = QPlainTextEdit()
        self.desc.setMaximumHeight(70)
        self.location = QLineEdit(str(default_parent or Path.home()))
        browse = QPushButton("…")
        browse.clicked.connect(self._browse)
        loc = QWidget()
        row = QHBoxLayout(loc)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.location, 1)
        row.addWidget(browse)
        form = QFormLayout()
        form.addRow("Nome", self.name)
        form.addRow("Descrição", self.desc)
        form.addRow("Local", loc)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(False)
        self.name.textChanged.connect(
            lambda t: self.buttons.button(QDialogButtonBox.Ok).setEnabled(bool(t.strip())))
        lay = QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(self.buttons)

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Local do projeto", self.location.text())
        if d:
            self.location.setText(d)

    def result_values(self) -> tuple[Path, str, str]:
        name = self.name.text().strip()
        return Path(self.location.text()) / slugify(name), name, self.desc.toPlainText()

"""Gerenciamento de projetos: criar, abrir, salvar, salvar como, fechar.

Formato: uma pasta contendo project.json e subpastas (models, experiments,
results, exports). A gravação é atômica (arquivo temporário + os.replace) e
mantém project.json.bak com a versão anterior.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from application import event_manager as ev
from application.event_manager import EventManager
from core.exceptions import ProjectError, ProjectIOError, ProjectValidationError
from core.validation.project_schema import FORMAT_ID, SCHEMA_VERSION, validate_project_dict

log = logging.getLogger("nexus.project")

PROJECT_FILE = "project.json"
SUBDIRS = ("models", "experiments", "results", "exports")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ProjectManager:
    def __init__(self, events: Optional[EventManager] = None) -> None:
        self.events = events or EventManager()
        self.data: Optional[dict] = None
        self.path: Optional[Path] = None
        self.dirty = False

    # ---- estado ----
    @property
    def is_open(self) -> bool:
        return self.data is not None

    @property
    def name(self) -> str:
        return self.data["name"] if self.data else ""

    def _require_open(self) -> dict:
        if self.data is None or self.path is None:
            raise ProjectError("Nenhum projeto aberto")
        return self.data

    # ---- operações ----
    def create(self, directory: Path | str, name: str, description: str = "") -> dict:
        directory = Path(directory)
        if directory.exists() and any(directory.iterdir()):
            raise ProjectIOError(f"A pasta já existe e não está vazia: {directory}")
        data = {
            "format": FORMAT_ID,
            "schema_version": SCHEMA_VERSION,
            "id": str(uuid.uuid4()),
            "name": name.strip(),
            "description": description,
            "created": _now(),
            "modified": _now(),
            "models": [],
            "experiments": [],
            "settings": {"units": "SI"},
        }
        validate_project_dict(data)
        try:
            for sub in SUBDIRS:
                (directory / sub).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ProjectIOError(f"Não foi possível criar {directory}: {exc}") from exc
        self._write(directory, data)
        self._set(data, directory, dirty=False)
        log.info("Projeto criado: %s (%s)", data["name"], directory)
        self.events.emit(ev.PROJECT_OPENED, project=self)
        return data

    def open(self, directory: Path | str) -> dict:
        directory = Path(directory)
        file = directory / PROJECT_FILE
        if not file.is_file():
            raise ProjectIOError(f"project.json não encontrado em {directory}")
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ProjectValidationError(f"project.json corrompido: {exc}") from exc
        except OSError as exc:
            raise ProjectIOError(f"Falha ao ler {file}: {exc}") from exc
        validate_project_dict(data)
        for sub in SUBDIRS:
            (directory / sub).mkdir(exist_ok=True)
        self._set(data, directory, dirty=False)
        log.info("Projeto aberto: %s (%s)", data["name"], directory)
        self.events.emit(ev.PROJECT_OPENED, project=self)
        return data

    def save(self) -> None:
        data = self._require_open()
        data["modified"] = _now()
        self._write(self.path, data)  # type: ignore[arg-type]
        self.dirty = False
        log.info("Projeto salvo: %s", self.path)
        self.events.emit(ev.PROJECT_SAVED, project=self)

    def save_as(self, directory: Path | str) -> None:
        data = self._require_open()
        target = Path(directory)
        if target.exists() and any(target.iterdir()):
            raise ProjectIOError(f"A pasta de destino já existe e não está vazia: {target}")
        try:
            shutil.copytree(self.path, target, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("*.tmp", "*.bak"))
        except OSError as exc:
            raise ProjectIOError(f"Falha ao copiar projeto: {exc}") from exc
        self.path = target
        self.save()
        log.info("Projeto salvo como: %s", target)

    def close(self) -> None:
        if self.data is None:
            return
        name = self.name
        self.data, self.path, self.dirty = None, None, False
        log.info("Projeto fechado: %s", name)
        self.events.emit(ev.PROJECT_CLOSED)

    def update_metadata(self, name: Optional[str] = None, description: Optional[str] = None) -> None:
        data = self._require_open()
        new = dict(data)
        if name is not None:
            new["name"] = name.strip()
        if description is not None:
            new["description"] = description
        validate_project_dict(new)  # levanta antes de alterar o estado
        if new == data:
            return
        data.update(new)
        self.dirty = True
        self.events.emit(ev.PROJECT_CHANGED, project=self)

    # ---- internos ----
    def _set(self, data: dict, path: Path, dirty: bool) -> None:
        self.data, self.path, self.dirty = data, path, dirty

    @staticmethod
    def _write(directory: Path, data: dict) -> None:
        file = directory / PROJECT_FILE
        tmp = directory / (PROJECT_FILE + ".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
                fh.flush()
                os.fsync(fh.fileno())
            if file.exists():
                shutil.copy2(file, directory / (PROJECT_FILE + ".bak"))
            os.replace(tmp, file)
        except OSError as exc:
            raise ProjectIOError(f"Falha ao gravar {file}: {exc}") from exc

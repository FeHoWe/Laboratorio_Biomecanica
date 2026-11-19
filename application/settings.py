"""Configurações do app (config/settings.json) e dados do usuário (projetos recentes)."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

log = logging.getLogger("nexus.settings")

ROOT = Path(__file__).resolve().parent.parent
DEFAULTS = {"language": "pt-BR", "theme": "dark", "log_level": "INFO", "max_recent_projects": 8}


def user_dir() -> Path:
    base = os.environ.get("NEXUS_HOME")
    path = Path(base) if base else Path.home() / ".nexus_biomechanics"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_settings(file: Path | None = None) -> dict:
    file = file or ROOT / "config" / "settings.json"
    settings = dict(DEFAULTS)
    try:
        loaded = json.loads(file.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            settings.update({k: v for k, v in loaded.items() if k in DEFAULTS})
    except FileNotFoundError:
        log.warning("settings.json ausente; usando padrões")
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("settings.json inválido (%s); usando padrões", exc)
    return settings


class RecentProjects:
    def __init__(self, limit: int = 8, file: Path | None = None) -> None:
        self.limit = limit
        self.file = file or user_dir() / "recent.json"

    def list(self) -> list[str]:
        try:
            data = json.loads(self.file.read_text(encoding="utf-8"))
            return [p for p in data if isinstance(p, str)][: self.limit]
        except (OSError, json.JSONDecodeError):
            return []

    def add(self, path: Path | str) -> None:
        path = str(path)
        items = [p for p in self.list() if p != path]
        items.insert(0, path)
        try:
            self.file.write_text(json.dumps(items[: self.limit], indent=2), encoding="utf-8")
        except OSError:
            log.warning("Não foi possível gravar lista de recentes")

"""Inicialização: logs, configurações, objetos centrais."""
from __future__ import annotations

import sys
import logging
from dataclasses import dataclass
from pathlib import Path

from application.event_manager import EventManager
from application.project_manager import ProjectManager
from application.settings import RecentProjects, load_settings, user_dir
from infrastructure.logging.logger import setup_logging


@dataclass
class Context:
    settings: dict
    events: EventManager
    manager: ProjectManager
    recent: RecentProjects
    log_file: Path


def bootstrap() -> Context:
    settings = load_settings()
    log_file = setup_logging(user_dir() / "logs", settings["log_level"])
    log = logging.getLogger("nexus")

    def hook(exc_type, exc, tb):  # exceções não tratadas vão para o log
        log.critical("Exceção não tratada", exc_info=(exc_type, exc, tb))
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = hook
    events = EventManager()
    return Context(settings, events, ProjectManager(events),
                   RecentProjects(settings["max_recent_projects"]), log_file)

"""Barramento de eventos simples (publicar/assinar), independente de Qt."""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Callable

log = logging.getLogger("nexus.events")

PROJECT_OPENED = "project.opened"
PROJECT_CLOSED = "project.closed"
PROJECT_SAVED = "project.saved"
PROJECT_CHANGED = "project.changed"


class EventManager:
    def __init__(self) -> None:
        self._subs: dict[str, list[Callable[..., None]]] = defaultdict(list)

    def subscribe(self, event: str, handler: Callable[..., None]) -> None:
        if handler not in self._subs[event]:
            self._subs[event].append(handler)

    def unsubscribe(self, event: str, handler: Callable[..., None]) -> None:
        if handler in self._subs[event]:
            self._subs[event].remove(handler)

    def emit(self, event: str, **payload: Any) -> None:
        for handler in list(self._subs[event]):
            try:
                handler(**payload)
            except Exception:  # um assinante com erro não derruba os demais
                log.exception("Erro no handler do evento %s", event)

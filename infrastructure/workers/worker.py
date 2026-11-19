"""Execução de tarefas pesadas fora da thread da interface, com progresso e cancelamento."""
from __future__ import annotations

import logging
import threading
from typing import Any, Callable

from PySide6.QtCore import QThread, Signal

from core.exceptions import SimulationCancelled

log = logging.getLogger("nexus.worker")


class TaskThread(QThread):
    """Executa fn(progress_cb, should_cancel) em outra thread.

    Sinais (entregues na thread da GUI): progress(int 0-100), succeeded(obj), failed(str), cancelled().
    """
    progress = Signal(int)
    succeeded = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, fn: Callable[[Callable[[int], None], Callable[[], bool]], Any], parent=None) -> None:
        super().__init__(parent)
        self._fn = fn
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    def run(self) -> None:
        try:
            result = self._fn(self.progress.emit, self._cancel.is_set)
        except SimulationCancelled:
            log.info("Tarefa cancelada")
            self.cancelled.emit()
        except Exception as exc:
            log.exception("Falha na tarefa")
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(result)

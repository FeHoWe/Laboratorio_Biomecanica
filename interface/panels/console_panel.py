"""Console de logs (recebe registros do logger 'nexus')."""
from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QTextCharFormat
from PySide6.QtWidgets import QPlainTextEdit

from interface import theme


class _Emitter(QObject):
    message = Signal(str, int)


class QtLogHandler(logging.Handler):
    """Handler thread-safe: emite sinal Qt, entregue na thread da GUI."""

    def __init__(self) -> None:
        super().__init__()
        self.emitter = _Emitter()
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.emitter.message.emit(self.format(record), record.levelno)
        except RuntimeError:  # objeto Qt já destruído
            pass


class ConsolePanel(QPlainTextEdit):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumBlockCount(5000)
        self.handler = QtLogHandler()
        self.handler.emitter.message.connect(self.append_line)
        logging.getLogger("nexus").addHandler(self.handler)

    def append_line(self, text: str, level: int) -> None:
        color = theme.TEXT
        if level >= logging.ERROR:
            color = theme.ERR
        elif level >= logging.WARNING:
            color = theme.WARN
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        self.setCurrentCharFormat(fmt)
        self.appendPlainText(text)

    def detach(self) -> None:
        logging.getLogger("nexus").removeHandler(self.handler)

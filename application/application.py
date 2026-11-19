"""Aplicação Qt."""
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from application.bootstrap import Context, bootstrap
from application.version import APP_NAME, __version__
from interface import theme
from interface.main_window import MainWindow


def create_window(ctx: Context | None = None) -> tuple[QApplication, MainWindow]:
    ctx = ctx or bootstrap()
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setStyleSheet(theme.STYLESHEET)
    return app, MainWindow(ctx.manager, ctx.recent, ctx.log_file)


def run(argv: list[str]) -> int:
    app, win = create_window()
    win.show()
    if "--smoke-test" in argv:  # inicia, renderiza e encerra (verificação automática)
        from PySide6.QtCore import QTimer
        if "--screenshot" in argv:
            path = argv[argv.index("--screenshot") + 1]
            QTimer.singleShot(400, lambda: win.grab().save(path))
        QTimer.singleShot(900, app.quit)
    return app.exec()

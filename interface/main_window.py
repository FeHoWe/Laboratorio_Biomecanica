"""Janela principal."""
from __future__ import annotations

import importlib
import logging
import platform
import sys
from pathlib import Path

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (QDockWidget, QFileDialog, QInputDialog, QLabel, QMainWindow, QMessageBox,
                               QPlainTextEdit, QStackedWidget, QTabWidget)

from application import event_manager as ev
from application.project_manager import ProjectManager
from application.settings import RecentProjects
from application.version import APP_NAME, PHASE, __version__
from core.exceptions import NexusError
from interface.dashboard import Dashboard
from interface.dialogs.new_project_dialog import NewProjectDialog
from interface.panels.component_tree import ComponentTree
from interface.panels.console_panel import ConsolePanel
from interface.panels.properties_panel import PropertiesPanel
from interface.widgets.viewport_placeholder import ViewportPlaceholder

log = logging.getLogger("nexus.ui")

PLANNED = {
    "Modelo": [("Novo modelo de membro inferior", "Fase 2"), ("Editar articulações", "Fase 2")],
    "Biomecânica": [("Cinemática direta/inversa", "Fase 3"), ("Torque e forças", "Fase 3")],
    "Simulação": [("Executar simulação", "Fase 3"), ("Integração MuJoCo", "Fase 6")],
    "Análise": [("Gráficos de ângulo/torque", "Fase 5"), ("Comparar modelos", "Fase 4")],
    "Pesquisa": [("Experimento BIO-001", "Fase 5"), ("Exportar CSV/PDF", "Fase 5")],
}
OPTIONAL_LIBS = ["numpy", "scipy", "sympy", "vtk", "pyvista", "mujoco", "opensim", "pyqtgraph", "matplotlib"]


class MainWindow(QMainWindow):
    def __init__(self, manager: ProjectManager, recent: RecentProjects, log_file: Path | None = None) -> None:
        super().__init__()
        self.manager, self.recent, self.log_file = manager, recent, log_file
        self.resize(1360, 820)
        self._build_central()
        self._build_docks()
        self._build_menus()
        self._status = QLabel()
        self.statusBar().addPermanentWidget(self._status)
        manager.events.subscribe(ev.PROJECT_OPENED, self._refresh)
        manager.events.subscribe(ev.PROJECT_CLOSED, self._refresh)
        manager.events.subscribe(ev.PROJECT_SAVED, self._refresh)
        manager.events.subscribe(ev.PROJECT_CHANGED, self._refresh)
        self._refresh()
        log.info("%s v%s iniciado (%s)", APP_NAME, __version__, PHASE)

    # ---- construção ----
    def _build_central(self) -> None:
        self.stack = QStackedWidget()
        self.dashboard = Dashboard()
        self.viewport = ViewportPlaceholder()
        self.stack.addWidget(self.dashboard)
        self.stack.addWidget(self.viewport)
        self.setCentralWidget(self.stack)
        self.dashboard.new_requested.connect(self.new_project)
        self.dashboard.open_requested.connect(self.open_project)
        self.dashboard.recent_requested.connect(self.open_project_path)

    def _build_docks(self) -> None:
        self.tree = ComponentTree()
        self.props = PropertiesPanel()
        self.console = ConsolePanel()
        self.results = QPlainTextEdit("Nenhum resultado. Simulações serão implementadas nas Fases 3-5.")
        self.results.setReadOnly(True)
        self.tree.selection_info.connect(self.props.show_item)
        self.props.apply_requested.connect(self._apply_metadata)
        self.dock_tree = self._dock("Componentes", self.tree, Qt.LeftDockWidgetArea)
        self.dock_props = self._dock("Propriedades", self.props, Qt.RightDockWidgetArea)
        tabs = QTabWidget()
        tabs.addTab(self.console, "Console")
        tabs.addTab(self.results, "Resultados")
        self.dock_bottom = self._dock("Resultados e Console", tabs, Qt.BottomDockWidgetArea)

    def _dock(self, title, widget, area) -> QDockWidget:
        d = QDockWidget(title, self)
        d.setObjectName(title)
        d.setWidget(widget)
        self.addDockWidget(area, d)
        return d

    def _act(self, menu, text, slot, shortcut=None, enabled=True) -> QAction:
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.triggered.connect(slot)
        a.setEnabled(enabled)
        menu.addAction(a)
        return a

    def _build_menus(self) -> None:
        mb = self.menuBar()
        m = mb.addMenu("&Arquivo")
        self.act_new = self._act(m, "&Novo projeto…", self.new_project, QKeySequence.New)
        self.act_open = self._act(m, "&Abrir projeto…", self.open_project, QKeySequence.Open)
        self.recent_menu = m.addMenu("Projetos &recentes")
        m.addSeparator()
        self.act_save = self._act(m, "&Salvar", self.save_project, QKeySequence.Save)
        self.act_save_as = self._act(m, "Salvar &como…", self.save_project_as, "Ctrl+Shift+S")
        self.act_close = self._act(m, "&Fechar projeto", self.close_project, "Ctrl+W")
        m.addSeparator()
        self._act(m, "Sai&r", self.close, "Ctrl+Q")

        m = mb.addMenu("&Editar")
        self.act_rename = self._act(m, "&Renomear projeto…", self.rename_project, "F2")
        self._act(m, "Desfazer / Refazer (planejado)", lambda: None, enabled=False)

        m = mb.addMenu("E&xibir")
        for d in (self.dock_tree, self.dock_props, self.dock_bottom):
            m.addAction(d.toggleViewAction())
        m.addSeparator()
        self._act(m, "Limpar console", self.console.clear)

        for title, items in PLANNED.items():
            menu = mb.addMenu(title)
            for text, phase in items:
                self._act(menu, f"{text} (planejado — {phase})", lambda: None, enabled=False)

        m = mb.addMenu("&Ferramentas")
        self._act(m, "Diagnóstico do ambiente", self.diagnostics)
        self._act(m, "Abrir pasta de logs", self.open_logs)

        m = mb.addMenu("A&juda")
        self._act(m, "&Sobre", self.about)

    # ---- estado ----
    def _refresh(self, **_kw) -> None:
        pm = self.manager
        is_open = pm.is_open
        for a in (self.act_save, self.act_save_as, self.act_close, self.act_rename):
            a.setEnabled(is_open)
        self.stack.setCurrentWidget(self.viewport if is_open else self.dashboard)
        self.tree.populate(pm.data)
        if not is_open:
            self.props.clear()
        recents = self.recent.list()
        self.dashboard.set_recent(recents)
        self.recent_menu.clear()
        self.recent_menu.setEnabled(bool(recents))
        for p in recents:
            a = self.recent_menu.addAction(p)
            a.triggered.connect(lambda _=False, path=p: self.open_project_path(path))
        title = APP_NAME
        if is_open:
            title = f"{pm.name}{' *' if pm.dirty else ''} — {APP_NAME}"
            self._status.setText(f"{pm.path}  |  {'modificado' if pm.dirty else 'salvo'}")
        else:
            self._status.setText("Nenhum projeto aberto")
        self.setWindowTitle(title)

    def _guard(self, fn, *args) -> bool:
        try:
            fn(*args)
            return True
        except NexusError as exc:
            log.error("%s", exc)
            QMessageBox.critical(self, APP_NAME, str(exc))
        except Exception as exc:  # erro inesperado: registrar e informar
            log.exception("Erro inesperado")
            QMessageBox.critical(self, APP_NAME, f"Erro inesperado: {exc}")
        return False

    def _confirm_discard(self) -> bool:
        if not (self.manager.is_open and self.manager.dirty):
            return True
        r = QMessageBox.question(self, APP_NAME, "Há alterações não salvas. Salvar antes de continuar?",
                                 QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        if r == QMessageBox.Cancel:
            return False
        if r == QMessageBox.Save:
            return self._guard(self.manager.save)
        return True

    # ---- ações de arquivo ----
    def new_project(self) -> None:
        if not self._confirm_discard():
            return
        dlg = NewProjectDialog(parent=self)
        if dlg.exec():
            path, name, desc = dlg.result_values()
            if self._guard(self.manager.create, path, name, desc):
                self.recent.add(path)
                self._refresh()

    def open_project(self) -> None:
        if not self._confirm_discard():
            return
        d = QFileDialog.getExistingDirectory(self, "Abrir projeto (pasta com project.json)")
        if d:
            self.open_project_path(d, confirmed=True)

    def open_project_path(self, path: str, confirmed: bool = False) -> None:
        if not confirmed and not self._confirm_discard():
            return
        if self._guard(self.manager.open, path):
            self.recent.add(path)
            self._refresh()

    def save_project(self) -> None:
        self._guard(self.manager.save)

    def save_project_as(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Salvar como — escolha uma pasta vazia")
        if d and self._guard(self.manager.save_as, d):
            self.recent.add(d)
            self._refresh()

    def close_project(self) -> None:
        if self._confirm_discard():
            self.manager.close()

    def rename_project(self) -> None:
        name, ok = QInputDialog.getText(self, "Renomear projeto", "Novo nome:", text=self.manager.name)
        if ok:
            self._apply_metadata(name, self.manager.data["description"])

    def _apply_metadata(self, name: str, description: str) -> None:
        self._guard(self.manager.update_metadata, name, description)

    # ---- ferramentas / ajuda ----
    def diagnostics(self) -> None:
        log.info("Python %s | PySide6 %s | %s", sys.version.split()[0], pyside_version, platform.platform())
        for lib in OPTIONAL_LIBS:
            try:
                mod = importlib.import_module(lib)
                log.info("  [OK]  %s %s", lib, getattr(mod, "__version__", ""))
            except Exception:
                log.warning("  [AUSENTE]  %s (não integrada nesta fase)", lib)

    def open_logs(self) -> None:
        if self.log_file:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.log_file.parent)))

    def about(self) -> None:
        QMessageBox.about(self, f"Sobre {APP_NAME}",
                          f"<b>{APP_NAME}</b> v{__version__}<br>{PHASE}<br><br>"
                          "Plataforma de pesquisa e aprendizado computacional.<br>"
                          "Não é um dispositivo médico; sem precisão clínica.")

    def closeEvent(self, event) -> None:
        if self._confirm_discard():
            self.console.detach()
            event.accept()
        else:
            event.ignore()

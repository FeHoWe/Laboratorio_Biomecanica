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
                               QPlainTextEdit, QStackedWidget, QTabWidget, QVBoxLayout, QWidget)

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
from interface.dialogs.bio001_dialog import Bio001Dialog
from interface.widgets.animation_2d import Animation2D
from interface.widgets.viewport_placeholder import ViewportPlaceholder
from PySide6.QtCore import Qt as _Qt  # noqa: F401
from research.experiments import bio001, passive_sim
from infrastructure.workers.worker import TaskThread
from interface.dialogs.passive_dialog import PassiveDialog
from PySide6.QtWidgets import QProgressDialog

log = logging.getLogger("nexus.ui")

PLANNED = {
    "Modelo": [("Editor 3D de modelo e articulações", "Fase 2"), ("Importar STL", "Fase 2")],
    "Biomecânica": [("Modelo de membro inferior com 3 segmentos", "Fase 4"), ("Músculos / OpenSim", "Fase 6")],
    "Simulação": [("Simulação dinâmica interativa", "Fase 4"), ("Integração MuJoCo", "Fase 6")],
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
        self.tree.selection_info.connect(lambda *_: self.act_rerun.setEnabled(
            self.manager.is_open and self._selected_experiment() is not None))
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
        self.viewport = QTabWidget()  # área central quando há projeto aberto
        self.viewport3d = ViewportPlaceholder()
        self.anim = Animation2D()
        self.plot_host = QWidget()
        self.plot_layout = QVBoxLayout(self.plot_host)
        self.plot_layout.addWidget(QLabel("Execute BIO-001 (menu Pesquisa) para ver os gráficos."))
        self.viewport.addTab(self.viewport3d, "Viewport 3D (planejado)")
        self.viewport.addTab(self.anim, "Animação 2D")
        self.viewport.addTab(self.plot_host, "Gráficos BIO-001")
        self.last_result: dict | None = None
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
        self.results = QPlainTextEdit("Nenhum resultado ainda. Use Pesquisa > Novo experimento BIO-001.")
        self.results.setReadOnly(True)
        self.tree.selection_info.connect(self.props.show_item)
        self.props.apply_requested.connect(self._apply_metadata)
        self.dock_tree = self._dock("Componentes", self.tree, Qt.LeftDockWidgetArea)
        self.dock_props = self._dock("Propriedades", self.props, Qt.RightDockWidgetArea)
        tabs = QTabWidget()
        self.bottom_tabs = tabs
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
        self.menus: dict = {}
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
            self.menus[title] = menu
            for text, phase in items:
                self._act(menu, f"{text} (planejado — {phase})", lambda: None, enabled=False)

        sim = self.menus["Simulação"]
        sim.clear()
        self.act_passive = self._act(sim, "Dinâmica passiva SIM-001 (pêndulo duplo)…", self.new_passive, "Ctrl+Shift+P", enabled=False)
        self._act(sim, "Integração MuJoCo (planejado — Fase 6)", lambda: None, enabled=False)

        m = mb.addMenu("A&nálise")
        self.act_compare = self._act(m, "Comparação A vs B (último BIO-001)", self.show_comparison, enabled=False)
        self.act_png = self._act(m, "Exportar gráficos (PNG)…", self.export_png, enabled=False)
        self._act(m, "Análises avançadas / IA (planejado — Fase 6)", lambda: None, enabled=False)

        m = mb.addMenu("&Pesquisa")
        self.act_bio = self._act(m, "Novo experimento &BIO-001…", self.new_bio001, "Ctrl+B", enabled=False)
        self.act_rerun = self._act(m, "Reexecutar experimento selecionado", self.rerun_selected, enabled=False)
        m.addSeparator()
        self.act_csv = self._act(m, "Exportar CSV…", self.export_csv, enabled=False)
        self.act_md = self._act(m, "Exportar relatório técnico (.md)…", self.export_report, enabled=False)
        self.act_pdf = self._act(m, "Exportar relatório PDF…", self.export_pdf_report, enabled=False)

        m = mb.addMenu("&Ferramentas")
        self._act(m, "Diagnóstico do ambiente", self.diagnostics)
        self._act(m, "Abrir pasta de logs", self.open_logs)

        m = mb.addMenu("A&juda")
        self._act(m, "&Sobre", self.about)

    # ---- estado ----
    def _refresh(self, **_kw) -> None:
        pm = self.manager
        is_open = pm.is_open
        for a in (self.act_save, self.act_save_as, self.act_close, self.act_rename, self.act_bio, self.act_passive):
            a.setEnabled(is_open)
        has = is_open and self.last_result is not None and self.last_result["id"] == bio001.EXPERIMENT_ID
        any_res = is_open and self.last_result is not None
        self.act_csv.setEnabled(any_res)
        for a in (self.act_md, self.act_png, self.act_compare, self.act_pdf):
            a.setEnabled(has)
        self.act_rerun.setEnabled(is_open and self._selected_experiment() is not None)
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

    # ---- pesquisa: BIO-001 ----
    def _selected_experiment(self):
        item = self.tree.currentItem()
        if item is None:
            return None
        kind, payload = item.data(0, _Qt.UserRole)
        return payload if kind == "experiment" and "params" in payload else None

    def new_bio001(self) -> None:
        dlg = Bio001Dialog(parent=self)
        if not dlg.exec():
            return
        params = dlg.params()
        res = self._run_bio001(params)
        if res is None:
            return
        self._guard(self.manager.add_experiment, bio001.EXPERIMENT_ID, params.to_dict(),
                    bio001.summary_dict(res), lambda path: bio001.export_csv(res, path))
        self._show_result(res)

    def rerun_selected(self) -> None:
        exp = self._selected_experiment()
        if exp and exp.get("type") == passive_sim.EXPERIMENT_ID:
            self.run_passive(passive_sim.PassiveParams.from_dict(exp["params"]), register=False)
            return
        if exp:
            res = self._run_bio001(bio001.Bio001Params.from_dict(exp["params"]))
            if res:
                self._show_result(res)
                log.info("Reexecução de %s concluída (determinística)", exp["id"])

    def _run_bio001(self, params):
        try:
            res = bio001.run(params)
        except NexusError as exc:
            log.error("%s", exc)
            QMessageBox.critical(self, APP_NAME, str(exc))
            return None
        for m in res["messages"]:
            log.warning(m) if m.startswith("AVISO") else log.info(m)
        return res

    def _show_result(self, res: dict) -> None:
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from visualization.charts.bio001_plots import make_figure
        self.last_result = res
        self.anim.set_result(res)
        while self.plot_layout.count():
            w = self.plot_layout.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.plot_layout.addWidget(FigureCanvasQTAgg(make_figure(res)))
        lines = [f"BIO-001 — resultados (parâmetros DEMONSTRATIVOS)", ""]
        for c in res["comparison"].values():
            lines.append(f"{c['label']}\n   A: {c['A'][0]:.4g} / {c['A'][1]:.4g}   B: {c['B'][0]:.4g} / {c['B'][1]:.4g}"
                         f"   (B/A: {', '.join('—' if r is None else f'{r:.3g}' for r in c['ratio_B_over_A'])})")
        lines += [""] + res["messages"]
        self.results.setPlainText("\n".join(lines))
        self.viewport.setCurrentWidget(self.anim)
        self._refresh()

    def show_comparison(self) -> None:
        self.viewport.setCurrentWidget(self.plot_host)
        self.bottom_tabs.setCurrentWidget(self.results)

    def _export(self, caption, filt, writer) -> None:
        path, _ = QFileDialog.getSaveFileName(self, caption, "", filt)
        if path and self.last_result and self._guard(writer, path):
            log.info("Exportado: %s", path)

    def export_csv(self) -> None:
        self._export("Exportar CSV", "CSV (*.csv)", lambda p: (passive_sim if self.last_result["id"] == passive_sim.EXPERIMENT_ID else bio001).export_csv(self.last_result, p))

    def export_pdf_report(self) -> None:
        from research.reports.pdf_report import export_pdf
        self._export("Exportar relatório PDF", "PDF (*.pdf)", lambda p: export_pdf(self.last_result, p))

    # ---- SIM-001 com worker ----
    def new_passive(self) -> None:
        dlg = PassiveDialog(parent=self)
        if not dlg.exec():
            return
        params = dlg.params()
        self.run_passive(params, register=True)

    def run_passive(self, params, register: bool) -> None:
        self._progress = QProgressDialog("Integrando dinâmica (RK4)…", "Cancelar", 0, 100, self)
        self._progress.setWindowTitle("SIM-001")
        self._progress.setMinimumDuration(0)
        self._progress.setAutoClose(False)
        self._progress.setAutoReset(False)
        self._thread = TaskThread(lambda prog, canc: passive_sim.run(params, prog, canc), self)
        self._progress.canceled.connect(self._thread.cancel)
        self._thread.progress.connect(self._progress.setValue)
        self._thread.succeeded.connect(lambda res: self._passive_done(res, params, register))
        self._thread.failed.connect(self._passive_failed)
        self._thread.cancelled.connect(lambda: (self._progress.close(), log.info("SIM-001 cancelada")))
        log.info("SIM-001 iniciada (thread separada)")
        self._thread.start()

    def _passive_failed(self, msg: str) -> None:
        self._progress.close()
        log.error("SIM-001 falhou: %s", msg)
        QMessageBox.critical(self, APP_NAME, msg)

    def _passive_done(self, res: dict, params, register: bool) -> None:
        self._progress.close()
        if register:
            self._guard(self.manager.add_experiment, passive_sim.EXPERIMENT_ID, params.to_dict(),
                        passive_sim.summary_dict(res), lambda path: passive_sim.export_csv(res, path))
        self._show_passive(res)

    def _show_passive(self, res: dict) -> None:
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        from visualization.charts.bio001_plots import make_passive_figure
        self.last_result = res
        self.anim.set_result(res)
        while self.plot_layout.count():
            w = self.plot_layout.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.plot_layout.addWidget(FigureCanvasQTAgg(make_passive_figure(res)))
        sm = res["A"]["summary"]
        self.results.setPlainText(f"SIM-001 — dinâmica passiva (DEMONSTRATIVO)\nPassos: {sm['steps']}\n"
                                  f"E inicial: {sm['energy_initial_j']:.6g} J  E final: {sm['energy_final_j']:.6g} J\n"
                                  f"Deriva relativa máxima: {sm['max_rel_energy_drift']:.3e}\n\n" + "\n".join(res["messages"]))
        self.viewport.setCurrentWidget(self.anim)
        self._refresh()

    def export_report(self) -> None:
        def w(p):
            Path(p).write_text(bio001.report_markdown(self.last_result), encoding="utf-8")
        self._export("Exportar relatório", "Markdown (*.md)", w)

    def export_png(self) -> None:
        from visualization.charts.bio001_plots import save_png
        self._export("Exportar gráficos", "PNG (*.png)", lambda p: save_png(self.last_result, p))

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

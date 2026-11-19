import pytest
from PySide6.QtWidgets import QMessageBox

from application.application import create_window
from application.bootstrap import Context
from application.event_manager import EventManager
from application.project_manager import ProjectManager
from application.settings import RecentProjects


@pytest.fixture
def win(qtbot, tmp_path):
    ev = EventManager()
    ctx = Context({}, ev, ProjectManager(ev), RecentProjects(file=tmp_path / "rec.json"), tmp_path / "n.log")
    _, w = create_window(ctx)
    qtbot.addWidget(w)
    return w


def test_menus_present(win):
    titles = [a.text().replace("&", "") for a in win.menuBar().actions()]
    assert titles == ["Arquivo", "Editar", "Exibir", "Modelo", "Biomecânica", "Simulação",
                      "Análise", "Pesquisa", "Ferramentas", "Ajuda"]


def test_no_project_disables_actions(win):
    assert not win.act_save.isEnabled() and not win.act_close.isEnabled()
    assert win.stack.currentWidget() is win.dashboard


def test_planned_items_are_disabled(win):
    for m in ("Modelo", "Simulação", "Pesquisa"):
        menu = next(a.menu() for a in win.menuBar().actions() if a.text() == m)
        assert all(not a.isEnabled() and "planejado" in a.text() for a in menu.actions())


def test_open_project_updates_ui(win, tmp_path):
    win.manager.create(tmp_path / "p", "Meu Projeto", "d")
    assert win.act_save.isEnabled()
    assert win.stack.currentWidget() is win.viewport
    assert win.tree.topLevelItem(0).text(0) == "Meu Projeto"
    assert win.props.name_edit.text() == "Meu Projeto"


def test_edit_apply_marks_dirty_and_saves(win, tmp_path):
    win.manager.create(tmp_path / "p", "A")
    win.props.name_edit.setText("B")
    win.props.apply_btn.click()
    assert win.manager.dirty and "*" in win.windowTitle()
    win.save_project()
    assert not win.manager.dirty and win.tree.topLevelItem(0).text(0) == "B"


def test_invalid_rename_shows_error(win, tmp_path, monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *a, **k: shown.append(a[2]))
    win.manager.create(tmp_path / "p", "A")
    win.props.name_edit.setText("")
    win.props.apply_btn.click()
    assert shown and win.manager.name == "A"


def test_close_project_returns_to_dashboard(win, tmp_path):
    win.manager.create(tmp_path / "p", "A")
    win.close_project()
    assert win.stack.currentWidget() is win.dashboard and win.tree.topLevelItemCount() == 0


def test_console_receives_logs(win):
    import logging
    logging.getLogger("nexus.test").warning("mensagem-de-teste")
    assert "mensagem-de-teste" in win.console.toPlainText()


def test_diagnostics_reports_missing_libs_honestly(win):
    win.diagnostics()
    text = win.console.toPlainText()
    assert "PySide6" in text and "[AUSENTE]" in text or "[OK]" in text

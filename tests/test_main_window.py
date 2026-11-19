import pytest
from PySide6.QtWidgets import QMessageBox

from application.application import create_window
from application.bootstrap import Context
from application.event_manager import EventManager
from application.project_manager import ProjectManager
from application.settings import RecentProjects


@pytest.fixture
def win(qtbot, tmp_path, monkeypatch):
    # fechamento com alterações abriria diálogo modal; nos testes, descartar
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.Discard)
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
    for m in ("Modelo", "Biomecânica"):
        menu = next(a.menu() for a in win.menuBar().actions() if a.text() == m)
        assert all(not a.isEnabled() and "planejado" in a.text() for a in menu.actions() if a is not win.act_limb)


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


def test_bio001_flow_in_gui(win, tmp_path, monkeypatch, qtbot):
    from interface.dialogs.bio001_dialog import Bio001Dialog
    monkeypatch.setattr(Bio001Dialog, "exec", lambda self: True)
    assert not win.act_bio.isEnabled()
    win.manager.create(tmp_path / "p", "P")
    assert win.act_bio.isEnabled() and not win.act_csv.isEnabled()
    win.new_bio001()
    assert win.last_result is not None and win.act_csv.isEnabled()
    assert win.manager.dirty and win.manager.data["experiments"][0]["id"] == "BIO-001-001"
    assert (tmp_path / "p" / "results" / "BIO-001-001.csv").is_file()
    assert "BIO-001" in win.results.toPlainText()
    assert win.anim.slider.maximum() == win.last_result["params"]["samples"] - 1
    win.anim.set_frame(50)
    assert "t = " in win.anim.label.text()
    # reexecução do experimento selecionado
    win.tree.setCurrentItem(win.tree.topLevelItem(0).child(1).child(0))
    assert win.act_rerun.isEnabled()
    before = win.last_result["A"]["tau"].copy()
    win.rerun_selected()
    assert (win.last_result["A"]["tau"] == before).all()


def test_exports_from_gui(win, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    from interface.dialogs.bio001_dialog import Bio001Dialog
    monkeypatch.setattr(Bio001Dialog, "exec", lambda self: True)
    win.manager.create(tmp_path / "p", "P")
    win.new_bio001()
    for name, fn in (("a.csv", win.export_csv), ("a.md", win.export_report), ("a.png", win.export_png)):
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, n=name: (str(tmp_path / n), ""))
        fn()
        assert (tmp_path / name).stat().st_size > 100


def test_passive_sim_gui_with_worker(win, tmp_path, qtbot, monkeypatch):
    from interface.dialogs.passive_dialog import PassiveDialog
    from research.experiments import passive_sim
    monkeypatch.setattr(PassiveDialog, "exec", lambda self: True)
    assert not win.act_passive.isEnabled()
    win.manager.create(tmp_path / "p", "P")
    assert win.act_passive.isEnabled()
    win.new_passive()
    qtbot.waitUntil(lambda: win.last_result is not None, timeout=30000)
    win._thread.wait()
    assert win.last_result["id"] == "SIM-001"
    assert win.manager.data["experiments"][0]["id"] == "SIM-001-001"
    assert (tmp_path / "p" / "results" / "SIM-001-001.csv").is_file()
    assert "Deriva" in win.results.toPlainText()
    assert win.act_csv.isEnabled() and not win.act_pdf.isEnabled()


def test_limb_model_flow(win, tmp_path):
    win.manager.create(tmp_path / "p", "P")
    assert win.act_limb.isEnabled()
    win.new_limb()
    assert len(win.manager.data["models"]) == 1 and win.limb is not None
    assert win.pose.isEnabled() and set(win.pose.sliders) == {"hip", "knee", "ankle"}
    win.pose.sliders["knee"].setValue(60)
    assert win.limb.angles_deg["knee"] == 60
    assert win.manager.data["models"][0]["angles_deg"]["knee"] == 60 and win.manager.dirty
    win.save_project()
    win.manager.close()
    win.manager.open(tmp_path / "p")
    win._refresh()
    win.tree.setCurrentItem(win.tree.topLevelItem(0).child(0).child(0))  # seleciona o modelo
    assert win.limb.angles_deg["knee"] == 60 and win.pose.sliders["knee"].value() == 60
    win.pose.reset()
    assert win.limb.angles_deg["knee"] == 0


def test_bio002_gui_flow_and_rerun_and_exports(win, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    from interface.dialogs.bio002_dialog import Bio002Dialog
    monkeypatch.setattr(Bio002Dialog, "exec", lambda self: True)
    win.manager.create(tmp_path / "p", "P")
    assert win.act_bio2.isEnabled()
    win.new_bio002()
    assert win.last_result["id"] == "BIO-002" and win.manager.data["experiments"][0]["id"] == "BIO-002-001"
    assert (tmp_path / "p" / "results" / "BIO-002-001.csv").is_file()
    assert win.anim.canvas.result["A"]["points"].shape[1] == 4  # animação com 3 segmentos
    assert win.act_pdf.isEnabled() and win.act_md.isEnabled() and win.act_png.isEnabled()
    for name, fn in (("b.csv", win.export_csv), ("b.md", win.export_report), ("b.png", win.export_png)):
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, n=name: (str(tmp_path / n), ""))
        fn()
        assert (tmp_path / name).stat().st_size > 100
    assert "jarrete" in (tmp_path / "b.md").read_text(encoding="utf-8")
    win.tree.setCurrentItem(win.tree.topLevelItem(0).child(1).child(0))
    before = win.last_result["B"]["tau"].copy()
    win.rerun_selected()
    assert (win.last_result["B"]["tau"] == before).all()


def test_exo001_gui_flow(win, tmp_path, monkeypatch):
    from PySide6.QtWidgets import QFileDialog
    from interface.dialogs.exo001_dialog import Exo001Dialog
    monkeypatch.setattr(Exo001Dialog, "exec", lambda self: True)
    assert not win.act_exo.isEnabled()
    win.manager.create(tmp_path / "p", "P")
    assert win.act_exo.isEnabled()
    win.new_exo001()
    assert win.last_result["id"] == "EXO-001"
    assert win.manager.data["experiments"][0]["id"] == "EXO-001-001"
    assert (tmp_path / "p" / "results" / "EXO-001-001.csv").is_file()
    assert "Pico humano" in win.results.toPlainText()
    assert win.act_csv.isEnabled() and win.act_md.isEnabled() and win.act_png.isEnabled()
    assert not win.act_compare.isEnabled() and win.act_pdf.isEnabled()
    for name, fn in (("e.csv", win.export_csv), ("e.md", win.export_report), ("e.png", win.export_png)):
        monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, n=name: (str(tmp_path / n), ""))
        fn()
        assert (tmp_path / name).stat().st_size > 100
    before = win.last_result["A"]["tau_human"].copy()
    win.tree.setCurrentItem(win.tree.findItems("EXO-001 #1", __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.MatchRecursive)[0])
    win.rerun_selected()
    assert (win.last_result["A"]["tau_human"] == before).all()

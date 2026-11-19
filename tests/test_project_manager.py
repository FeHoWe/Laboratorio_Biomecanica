import json

import pytest

from application.event_manager import EventManager
from application import event_manager as ev
from application.project_manager import ProjectManager
from core.exceptions import ProjectIOError, ProjectValidationError, ProjectError


@pytest.fixture
def pm():
    return ProjectManager(EventManager())


def test_create_makes_structure(pm, tmp_path):
    d = tmp_path / "p1"
    pm.create(d, "Teste", "desc")
    assert (d / "project.json").is_file()
    for sub in ("models", "experiments", "results", "exports"):
        assert (d / sub).is_dir()
    assert pm.is_open and not pm.dirty


def test_roundtrip(pm, tmp_path):
    d = tmp_path / "p"
    pm.create(d, "Perna", "d")
    pid = pm.data["id"]
    pm.close()
    assert not pm.is_open
    pm.open(d)
    assert pm.data["name"] == "Perna" and pm.data["id"] == pid


def test_create_refuses_nonempty_dir(pm, tmp_path):
    (tmp_path / "x").mkdir()
    (tmp_path / "x" / "a.txt").write_text("a")
    with pytest.raises(ProjectIOError):
        pm.create(tmp_path / "x", "N")


def test_invalid_name_rejected(pm, tmp_path):
    with pytest.raises(ProjectValidationError):
        pm.create(tmp_path / "q", "   ")


def test_corrupt_json(pm, tmp_path):
    d = tmp_path / "c"
    d.mkdir()
    (d / "project.json").write_text("{nao eh json")
    with pytest.raises(ProjectValidationError):
        pm.open(d)


def test_wrong_format_and_future_schema(pm, tmp_path):
    d = tmp_path / "w"
    pm.create(d, "A")
    data = json.loads((d / "project.json").read_text())
    pm.close()
    for patch in ({"format": "outro"}, {"schema_version": 99}, {"models": "x"}, {"created": "ontem"}):
        (d / "project.json").write_text(json.dumps({**data, **patch}))
        with pytest.raises(ProjectValidationError):
            pm.open(d)


def test_missing_file(pm, tmp_path):
    with pytest.raises(ProjectIOError):
        pm.open(tmp_path)


def test_metadata_dirty_save_and_backup(pm, tmp_path):
    d = tmp_path / "m"
    pm.create(d, "Antigo")
    pm.update_metadata(name="Novo")
    assert pm.dirty
    pm.save()
    assert not pm.dirty
    assert json.loads((d / "project.json").read_text())["name"] == "Novo"
    assert json.loads((d / "project.json.bak").read_text())["name"] == "Antigo"
    assert not (d / "project.json.tmp").exists()


def test_invalid_update_keeps_state(pm, tmp_path):
    pm.create(tmp_path / "i", "Ok")
    with pytest.raises(ProjectValidationError):
        pm.update_metadata(name="")
    assert pm.name == "Ok" and not pm.dirty


def test_save_as(pm, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    pm.create(a, "Orig")
    (a / "results" / "r.csv").write_text("x")
    pm.save_as(b)
    assert pm.path == b and (b / "results" / "r.csv").is_file() and (b / "project.json").is_file()
    assert (a / "project.json").is_file()


def test_save_as_refuses_nonempty(pm, tmp_path):
    pm.create(tmp_path / "a", "A")
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "f").write_text("1")
    with pytest.raises(ProjectIOError):
        pm.save_as(tmp_path / "b")


def test_operations_without_project(pm):
    with pytest.raises(ProjectError):
        pm.save()
    pm.close()  # não deve falhar


def test_events(pm, tmp_path):
    seen = []
    for e in (ev.PROJECT_OPENED, ev.PROJECT_CHANGED, ev.PROJECT_SAVED, ev.PROJECT_CLOSED):
        pm.events.subscribe(e, lambda _e=e, **kw: seen.append(_e))
    pm.create(tmp_path / "e", "E")
    pm.update_metadata(description="x")
    pm.save()
    pm.close()
    assert seen == [ev.PROJECT_OPENED, ev.PROJECT_CHANGED, ev.PROJECT_SAVED, ev.PROJECT_CLOSED]

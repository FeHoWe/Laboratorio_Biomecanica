import json
import logging

from application.event_manager import EventManager
from application.settings import RecentProjects, load_settings
from infrastructure.logging.logger import setup_logging


def test_event_handler_error_isolated():
    em, got = EventManager(), []
    em.subscribe("x", lambda **k: 1 / 0)
    em.subscribe("x", lambda **k: got.append(k["v"]))
    em.emit("x", v=5)
    assert got == [5]


def test_logging_writes_file_and_is_idempotent(tmp_path):
    f = setup_logging(tmp_path / "logs")
    setup_logging(tmp_path / "logs")
    logging.getLogger("nexus.t").info("olá")
    for h in logging.getLogger("nexus").handlers:
        h.flush()
    assert "olá" in f.read_text(encoding="utf-8")
    assert len([h for h in logging.getLogger("nexus").handlers if getattr(h, "_nexus_handler", False)]) == 2


def test_settings_defaults_and_corrupt(tmp_path):
    assert load_settings(tmp_path / "nao.json")["theme"] == "dark"
    bad = tmp_path / "s.json"
    bad.write_text("{{")
    assert load_settings(bad)["language"] == "pt-BR"
    ok = tmp_path / "ok.json"
    ok.write_text(json.dumps({"log_level": "DEBUG", "lixo": 1}))
    s = load_settings(ok)
    assert s["log_level"] == "DEBUG" and "lixo" not in s


def test_recent_projects(tmp_path):
    r = RecentProjects(limit=2, file=tmp_path / "r.json")
    for p in ("a", "b", "a", "c"):
        r.add(p)
    assert r.list() == ["c", "a"]

import json
import sqlite3

import pytest

from application.project_manager import ProjectManager
from infrastructure.database.history import DB_FILE, ExperimentHistory, flatten_metrics
from research.experiments import bio001, bio002


def test_flatten_metrics():
    m = flatten_metrics({"A": {"peak": [1.0, 2], "n": 3, "txt": "x", "ok": True, "bad": float("nan")}, "z": 5.5})
    assert m == {"A.peak[0]": 1.0, "A.peak[1]": 2.0, "A.n": 3.0, "z": 5.5}


def _project(tmp_path):
    pm = ProjectManager()
    pm.create(tmp_path / "p", "P")
    for scale in (1.0, 2.0):
        p = bio001.default_params()
        p.duration_s = scale
        r = bio001.run(p)
        pm.add_experiment(bio001.EXPERIMENT_ID, p.to_dict(), bio001.summary_dict(r))
    r2 = bio002.run(bio002.default_params())
    pm.add_experiment(bio002.EXPERIMENT_ID, bio002.default_params().to_dict(), bio002.summary_dict(r2))
    return pm


def test_rebuild_on_save_and_queries(tmp_path):
    pm = _project(tmp_path)
    pm.save()
    assert (tmp_path / "p" / DB_FILE).is_file()
    h = pm.history()
    assert h.types() == ["BIO-001", "BIO-002"]
    assert [e["id"] for e in h.list_experiments()] == ["BIO-001-001", "BIO-001-002", "BIO-002-001"]
    assert [e["id"] for e in h.list_experiments("BIO-002")] == ["BIO-002-001"]
    key = next(k for k in h.metric_names("BIO-001") if k == "A.peak_abs_power_w[0]")
    asc = h.list_experiments("BIO-001", key)
    desc = h.list_experiments("BIO-001", key, order_desc=True)
    assert [e["id"] for e in asc] == [e["id"] for e in reversed(desc)] and asc[0]["value"] <= asc[1]["value"]
    # experimento sem a métrica: valor None, vai para o fim; only_with_metric o filtra
    from exoskeleton.analysis import assist
    pe = assist.default_params()
    pm.add_experiment(assist.EXPERIMENT_ID, pe.to_dict(), assist.summary_dict(assist.run(pe)))
    pm.save()
    key = "A.peak_abs_power_w[0]"  # existe em BIO-001/002, não em EXO-001
    h = pm.history()
    mixed = h.list_experiments(None, key)
    assert mixed[-1]["value"] is None
    assert all(e["value"] is not None for e in h.list_experiments(None, key, only_with_metric=True))


def test_index_is_derived_and_reproducible(tmp_path):
    pm = _project(tmp_path)
    pm.save()
    db = tmp_path / "p" / DB_FILE
    db.unlink()
    pm.close()
    pm.open(tmp_path / "p")  # reconstrói
    assert len(pm.history().list_experiments()) == 3
    # valores do banco coincidem com o project.json
    con = sqlite3.connect(db)
    raw = con.execute("SELECT summary_json FROM experiments WHERE id='BIO-001-001'").fetchone()[0]
    con.close()
    assert json.loads(raw) == json.loads(json.dumps(pm.data["experiments"][0]["summary"]))


def test_corrupt_db_does_not_block_open_and_is_repaired(tmp_path):
    pm = _project(tmp_path)
    pm.save()
    pm.close()
    (tmp_path / "p" / DB_FILE).write_bytes(b"isto nao e um banco sqlite" * 50)
    pm.open(tmp_path / "p")  # não deve levantar exceção
    assert pm.is_open


def test_save_as_does_not_copy_stale_db_and_rebuilds(tmp_path):
    pm = _project(tmp_path)
    pm.save()
    pm.save_as(tmp_path / "q")
    assert len(ExperimentHistory(tmp_path / "q" / DB_FILE).list_experiments()) == 3

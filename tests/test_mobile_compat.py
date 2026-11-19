"""Projeto gerado pela versão mobile (JavaScript) deve abrir no desktop e reproduzir os resultados."""
import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from application.project_manager import ProjectManager
from biomechanics.human_model.lower_limb import LowerLimbModel
from research.experiments import bio001, bio002, passive_sim

DATA = Path(__file__).parent / "data" / "mobile_project.json"


@pytest.fixture
def pm(tmp_path):
    d = tmp_path / "mobile"
    d.mkdir()
    shutil.copy(DATA, d / "project.json")
    m = ProjectManager()
    m.open(d)
    return m


def test_mobile_project_opens_and_validates(pm):
    assert pm.name == "Teste mobile" and len(pm.data["models"]) == 1 and len(pm.data["experiments"]) == 4


def test_model_from_mobile_loads_and_matches_pose(pm):
    m = LowerLimbModel.from_dict(pm.data["models"][0])
    assert m.angles_deg["knee"] == 70
    assert LowerLimbModel().to_dict()["segments"] == {k: v for k, v in pm.data["models"][0]["segments"].items()}


def test_bio001_reproduces_mobile_summary(pm):
    exp = next(e for e in pm.data["experiments"] if e["type"] == "BIO-001")
    res = bio001.run(bio001.Bio001Params.from_dict(exp["params"]))
    for key in ("A", "B"):
        for field, vals in exp["summary"][key].items():
            assert np.allclose(res[key]["summary"][field], vals, rtol=1e-9, atol=1e-12), (key, field)


def test_sim001_reproduces_mobile_summary(pm):
    exp = next(e for e in pm.data["experiments"] if e["type"] == "SIM-001")
    res = passive_sim.run(passive_sim.PassiveParams.from_dict(exp["params"]))
    a, b = res["A"]["summary"], exp["summary"]["A"]
    assert a["steps"] == b["steps"]
    assert a["energy_initial_j"] == pytest.approx(b["energy_initial_j"], rel=1e-9)
    assert a["energy_final_j"] == pytest.approx(b["energy_final_j"], rel=1e-9)


def test_bio002_reproduces_mobile_summary(pm):
    exp = next(e for e in pm.data["experiments"] if e["type"] == "BIO-002")
    res = bio002.run(bio002.Bio002Params.from_dict(exp["params"]))
    for key in ("A", "B"):
        for field, vals in exp["summary"][key].items():
            assert np.allclose(res[key]["summary"][field], vals, rtol=1e-6, atol=1e-8), (key, field)


def test_exo001_reproduces_mobile_summary(pm):
    from exoskeleton.analysis import assist as ex
    exp = next(e for e in pm.data["experiments"] if e["type"] == "EXO-001")
    res = ex.run(ex.Exo001Params.from_dict(exp["params"]))
    for field, val in exp["summary"]["A"].items():
        if isinstance(val, str):
            assert res["A"]["summary"][field] == val
        else:
            assert np.allclose(res["A"]["summary"][field], val, rtol=1e-6, atol=1e-8), field


def test_limb3d_js_matches_python_segments():
    """Geometria 3D do celular (limb3D) coincide com LowerLimbModel.segment_endpoints/total_com."""
    poses = json.loads((DATA.parent / "limb3d_js.json").read_text(encoding="utf-8"))
    assert len(poses) == 4
    for p in poses:
        m = LowerLimbModel()
        for joint, a in zip(("hip", "knee", "ankle"), p["angles"]):
            m.set_angle(joint, a)
        ep = m.segment_endpoints()
        for name, (a, b) in ep.items():
            ja, jb = p["l"]["segs"][name]
            assert np.allclose(a, ja, atol=1e-9) and np.allclose(b, jb, atol=1e-9), (p["angles"], name)
        assert np.allclose(m.total_com(), p["l"]["com"], atol=1e-9)


def test_flatten_metrics_js_matches_python(pm):
    from infrastructure.database.history import flatten_metrics
    js = json.loads((DATA.parent / "mobile_metrics.json").read_text(encoding="utf-8"))
    assert len(js) == len(pm.data["experiments"])
    for item, exp in zip(js, pm.data["experiments"]):
        assert item["id"] == exp["id"]
        py = flatten_metrics(exp["summary"])
        assert set(py) == set(item["m"]) and len(py) >= 5
        for k, v in py.items():
            assert item["m"][k] == pytest.approx(v, rel=1e-12, abs=1e-15), k

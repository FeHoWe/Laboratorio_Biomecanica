"""Projeto gerado pela versão mobile (JavaScript) deve abrir no desktop e reproduzir os resultados."""
import json
import shutil
from pathlib import Path

import numpy as np
import pytest

from application.project_manager import ProjectManager
from biomechanics.human_model.lower_limb import LowerLimbModel
from research.experiments import bio001, passive_sim

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
    assert pm.name == "Teste mobile" and len(pm.data["models"]) == 1 and len(pm.data["experiments"]) == 2


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

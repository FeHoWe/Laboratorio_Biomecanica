import csv
import json

import numpy as np
import pytest

from application.project_manager import ProjectManager
from biomechanics.force_engine.planar_dynamics import G
from research.experiments import bio002 as b


def test_defaults_flagged_and_deterministic():
    p = b.default_params()
    assert "DEMONSTRATIVO" in p.model_a.source
    r1, r2 = b.run(p), b.run(b.Bio002Params.from_dict(json.loads(json.dumps(p.to_dict()))))
    assert np.array_equal(r1["A"]["tau"], r2["A"]["tau"]) and r1["comparison"] == r2["comparison"]
    assert r1["A"]["q"].shape == (151, 3) and r1["A"]["points"].shape == (151, 4, 2)


def test_static_horizontal_pose_matches_analytic():
    p = b.default_params()
    for m in (p.model_a, p.model_b):
        m.q_start_deg = m.q_end_deg = [0.0, 0.0, 0.0]
        m.com_fracs = [0.5, 0.5, 0.5]
    r = b.run(p)
    A = p.model_a
    L, m = A.lengths_m, A.masses_kg
    t3 = G * m[2] * 0.5 * L[2]
    t2 = G * (m[1] * 0.5 * L[1] + m[2] * (L[1] + 0.5 * L[2]))
    t1 = G * (m[0] * 0.5 * L[0] + m[1] * (L[0] + 0.5 * L[1]) + m[2] * (L[0] + L[1] + 0.5 * L[2]))
    assert np.allclose(r["A"]["tau"], [t1, t2, t3])


def test_work_equals_energy_change():
    p = b.default_params()
    r = b.run(p)
    chain = p.model_a.chain()
    a = r["A"]
    dE = chain.energy(a["q"][-1], a["qd"][-1]) - chain.energy(a["q"][0], a["qd"][0])
    assert sum(a["summary"]["work_j"]) == pytest.approx(dE, rel=5e-3, abs=1e-3)


def test_validation():
    p = b.default_params()
    p.model_a.masses_kg = [1.0, 1.0]
    with pytest.raises(b.Bio002Error):
        b.run(p)
    p = b.default_params()
    p.model_b.lengths_m[0] = 0
    with pytest.raises(b.Bio002Error):
        b.run(p)
    p = b.default_params()
    p.samples = 2
    with pytest.raises(b.Bio002Error):
        b.run(p)


def test_csv_report_and_project(tmp_path):
    p = b.default_params()
    r = b.run(p)
    f = tmp_path / "r.csv"
    b.export_csv(r, f)
    rows = list(csv.reader(open(f, encoding="utf-8")))
    assert len(rows) == 1 + 2 * p.samples and "tau3_Nm" in rows[0]
    md = b.report_markdown(r)
    for s in ("Parâmetros de entrada", "Hipóteses", "Método", "Limitações", "DEMONSTRATIVO", "jarrete"):
        assert s in md
    pm = ProjectManager()
    pm.create(tmp_path / "p", "P")
    e = pm.add_experiment(b.EXPERIMENT_ID, p.to_dict(), b.summary_dict(r), lambda path: b.export_csv(r, path))
    pm.save(); pm.close(); pm.open(tmp_path / "p")
    again = b.run(b.Bio002Params.from_dict(pm.data["experiments"][0]["params"]))
    assert b.summary_dict(again)["B"] == pm.data["experiments"][0]["summary"]["B"] and e["id"] == "BIO-002-001"

import csv
import json
import math

import numpy as np
import pytest

from application.project_manager import ProjectManager
from biomechanics.force_engine.planar_dynamics import G
from research.experiments import bio001 as b


def test_default_params_flagged_demonstrative():
    p = b.default_params()
    assert "DEMONSTRATIVO" in p.model_a.source and "DEMONSTRATIVO" in p.model_b.source


def test_deterministic_and_roundtrip_params():
    p = b.default_params()
    r1, r2 = b.run(p), b.run(b.Bio001Params.from_dict(json.loads(json.dumps(p.to_dict()))))
    for k in ("A", "B"):
        assert np.array_equal(r1[k]["tau"], r2[k]["tau"])
    assert r1["comparison"] == r2["comparison"]


def test_static_pose_matches_analytic_torque():
    p = b.default_params()
    for m in (p.model_a, p.model_b):
        m.q1_end_deg, m.q2_end_deg = m.q1_start_deg, m.q2_start_deg
        m.q1_start_deg, m.q2_start_deg = 0.0, 0.0
        m.q1_end_deg, m.q2_end_deg = 0.0, 0.0
        m.com1 = m.com2 = 0.5
    r = b.run(p)
    A = p.model_a
    expected1 = G * (A.m1 * 0.5 * A.l1 + A.m2 * (A.l1 + 0.5 * A.l2))
    expected2 = G * A.m2 * 0.5 * A.l2
    assert np.allclose(r["A"]["tau"][:, 0], expected1)
    assert np.allclose(r["A"]["tau"][:, 1], expected2)
    assert max(r["A"]["summary"]["peak_abs_power_w"]) == pytest.approx(0, abs=1e-9)


def test_tip_force_changes_torque_by_jt_f():
    p = b.default_params()
    r0 = b.run(p)
    p.model_a.tip_force_n = (0.0, 50.0)
    r1 = b.run(p)
    arm = p.model_a.arm()
    q = r0["A"]["q"][10]
    diff = r0["A"]["tau"][10] - r1["A"]["tau"][10]
    assert np.allclose(diff, arm.chain.jacobian(*q).T @ [0, 50.0])


def test_work_energy_consistency():
    """Trabalho total dos torques = ΔE mecânica (aqui parte em repouso e termina em repouso)."""
    r = b.run(b.default_params())
    p = b.default_params()
    arm = p.model_a.arm()
    a = r["A"]
    dE = arm.energy(a["q"][-1], a["qd"][-1]) - arm.energy(a["q"][0], a["qd"][0])
    assert sum(a["summary"]["work_j"]) == pytest.approx(dE, rel=5e-3, abs=1e-3)


def test_validation_errors():
    p = b.default_params()
    p.model_a.l1 = 0
    with pytest.raises(b.ExperimentError):
        b.run(p)
    p = b.default_params()
    p.samples = 2
    with pytest.raises(b.ExperimentError):
        p.validate()
    p = b.default_params()
    p.duration_s = 0.01
    assert any("AVISO" in m for m in b.run(p)["messages"])


def test_csv_export(tmp_path):
    r = b.run(b.default_params())
    f = tmp_path / "r.csv"
    b.export_csv(r, f)
    rows = list(csv.reader(open(f, encoding="utf-8")))
    assert rows[0] == b.CSV_HEADER
    assert len(rows) == 1 + 2 * r["params"]["samples"]
    last_a = [x for x in rows if x[0] == "A"][-1]
    assert float(last_a[2]) == pytest.approx(r["params"]["model_a"]["q1_end_deg"])
    assert float(rows[1][8]) == pytest.approx(r["A"]["tau"][0, 0], rel=1e-6)
    assert not (tmp_path / "r.csv.tmp").exists()


def test_report_contains_required_sections():
    md = b.report_markdown(b.run(b.default_params()))
    for s in ("Parâmetros de entrada", "Hipóteses", "Método", "Resultados", "validação", "Limitações", "DEMONSTRATIVO"):
        assert s in md


def test_experiment_persisted_in_project_and_reproducible(tmp_path):
    pm = ProjectManager()
    pm.create(tmp_path / "p", "P")
    p = b.default_params()
    res = b.run(p)
    entry = pm.add_experiment(b.EXPERIMENT_ID, p.to_dict(), b.summary_dict(res),
                              csv_writer=lambda path: b.export_csv(res, path))
    pm.save()
    pm.close()
    pm.open(tmp_path / "p")
    e = pm.data["experiments"][0]
    assert e["id"] == "BIO-001-001" and (tmp_path / "p" / e["results_file"]).is_file()
    again = b.run(b.Bio001Params.from_dict(e["params"]))
    assert b.summary_dict(again)["A"] == e["summary"]["A"]
    assert pm.add_experiment(b.EXPERIMENT_ID, p.to_dict(), {})["id"] == "BIO-001-002"

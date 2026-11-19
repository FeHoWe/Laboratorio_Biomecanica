"""ETAPA 5 — BIO-003: execução determinística, física, exportações, validações e persistência/histórico."""
import csv
import json

import numpy as np
import pytest

from application.project_manager import ProjectManager
from research.experiments import bio003
from research.reports.pdf_report import export_pdf
from visualization.charts.bio001_plots import make_bio003_figure, save_png


def small(**kw):
    p = bio003.default_params()
    p.duration_s, p.dt_s = 0.2, 0.002
    for k, v in kw.items():
        setattr(p, k, v)
    return p


@pytest.fixture(scope="module")
def free():
    return bio003.run(small())


def test_free_run_conserves_energy_and_reports_consistent_summary(free):
    s = free["summary"]
    assert s["conservative_run"] and s["energy_drift_rel"] < 1e-5
    assert free["q"].shape == (101, 6) and np.all(np.isfinite(free["tau"]))
    assert np.allclose(free["tau"], 0) and np.isclose(free["me"][0], free["ke"][0] + free["pe"][0])
    assert s["mass_matrix_min_eig_q0"] > 0 and any("demonstrativos" in m for m in free["messages"])
    # a ponta do pé reportada é a FK da trajetória
    assert np.allclose(free["foot_tip"][0], bio003.build_chain(small()).point_world("foot", [0.24, 0, 0], bio003.build_chain(small()).forward_kinematics(free["q"][0])))


def test_deterministic_rerun_and_params_roundtrip(free):
    p = small()
    p2 = bio003.Bio003Params.from_dict(json.loads(json.dumps(p.to_dict())))
    b = bio003.run(p2)
    assert np.array_equal(free["q"], b["q"]) and np.array_equal(free["me"], b["me"])


def test_torque_run_work_energy_and_no_conservation_claim():
    p = small(tau_const_nm=[3.0, 0, 0, 2.0, 0, 0], tau_amp_nm=[2.0, 0, 0, 0, 0, 0])
    r = bio003.run(p)
    s = r["summary"]
    assert not s["conservative_run"]
    assert s["work_energy_residual_j"] < 5e-3 * max(1.0, abs(s["work_torques_j"]), abs(s["delta_energy_j"]))
    assert np.isclose(r["tau"][0, 0], 3.0) and np.isclose(r["tau"][50, 0], 3.0 + 2.0 * np.sin(2 * np.pi * 1.0 * r["t"][50]))


def test_rk4_and_adaptive_agree_and_progress_is_integer_percent():
    prog = []
    a = bio003.run(small(), progress=prog.append)
    b = bio003.run(small(method="adaptive", dt_s=0.01))
    assert prog[0] == 0 and prog[-1] == 100 and all(isinstance(x, int) for x in prog)
    assert np.allclose(a.get("q")[::5], b["q"], atol=1e-4)


def test_cancel_stops_run():
    from core.exceptions import SimulationCancelled
    n = {"k": 0}
    def c():
        n["k"] += 1
        return n["k"] > 3
    with pytest.raises(SimulationCancelled):
        bio003.run(small(), cancelled=c)


@pytest.mark.parametrize("change,msg", [
    (dict(q0_deg=[500, 0, 0, 0, 0, 0]), "fora dos limites"), (dict(q0_deg=[0] * 5), "6 valores"), (dict(duration_s=0), "duração"),
    (dict(dt_s=1e-9, duration_s=10), "Passos demais"), (dict(method="euler"), "método"), (dict(limits_deg=[[1, 0]] * 6), "mín < máx"),
    (dict(gravity_m_s2=(0, float("nan"), 0)), "gravidade"), (dict(tau_freq_hz=[-1] * 6), "frequências")])
def test_validation_errors(change, msg):
    with pytest.raises(bio003.Bio003Error, match=msg):
        bio003.run(small(**change))


def test_invalid_segment_and_zero_gravity_and_limit_warning():
    p = small()
    p.segments["femur"]["mass_kg"] = -1
    with pytest.raises(bio003.Bio003Error, match="Segmento"):
        p.validate()
    z = bio003.run(small(gravity_m_s2=(0.0, 0.0, 0.0), qd0_deg_s=[30, 0, 0, 0, 0, 0]))
    assert np.allclose(z["pe"], z["pe"][0]) and z["summary"]["energy_drift_rel"] < 1e-5
    w = bio003.run(small(q0_deg=[118, 0, 0, 0, 0, 0], qd0_deg_s=[200, 0, 0, 0, 0, 0]))   # passa do limite de flexão (120°)
    assert w["summary"]["limit_violations"] > 0 and any("limite articular" in m for m in w["messages"])


def test_export_csv_report_png_pdf(free, tmp_path):
    csv_p, md, png, pdf = (tmp_path / n for n in ("r.csv", "r.md", "r.png", "r.pdf"))
    bio003.export_csv(free, csv_p)
    rows = list(csv.reader(open(csv_p, encoding="utf-8")))
    assert len(rows) == 102 and rows[0][0] == "t_s" and "q_quadril_flexao_deg" in rows[0] and "ME_J" in rows[0]
    assert np.isclose(float(rows[1][1 + 0]), np.degrees(free["q"][0, 0]), atol=1e-6)
    text = bio003.report_markdown(free)
    assert "Não é dispositivo médico" in text and "DEMONSTRATIVO" in text.upper() and "quadril_flexao" in text
    save_png(free, png)
    export_pdf(free, pdf)
    assert png.stat().st_size > 5000 and pdf.read_bytes()[:4] == b"%PDF"
    assert len(make_bio003_figure(free).axes) == 6


def test_persist_in_project_history_and_reopen_rerun(free, tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_HOME", str(tmp_path / "home"))
    m = ProjectManager()
    m.create(tmp_path / "proj", "P")
    p = small()
    m.add_experiment(bio003.EXPERIMENT_ID, p.to_dict(), bio003.summary_dict(free), lambda path: bio003.export_csv(free, path))
    m.save()
    m2 = ProjectManager()
    m2.open(tmp_path / "proj")
    exp = [e for e in m2.data["experiments"] if e["type"] == "BIO-003"][0]
    again = bio003.run(bio003.Bio003Params.from_dict(exp["params"]))
    assert np.array_equal(again["q"], free["q"])
    h = m2.history()
    assert "A.energy_drift_rel" in h.metric_names("BIO-003")
    rows = h.list_experiments("BIO-003", "A.energy_drift_rel")
    assert len(rows) == 1 and rows[0]["value"] is not None and rows[0]["value"] < 1e-5

import json

import numpy as np
import pytest

from application.project_manager import ProjectManager
from exoskeleton.actuators.actuator import Actuator, ActuatorError
from exoskeleton.analysis import assist as ex


def test_actuator_curve_and_power():
    a = Actuator(tau_stall_nm=40, omega_noload_rad_s=8, efficiency=0.5)
    assert a.tau_limit(0) == 40 and a.tau_limit(4) == pytest.approx(20) and a.tau_limit(8) == 0 and a.tau_limit(-20) == 0
    assert a.saturate(100, 0) == (40, True) and a.saturate(-100, 0) == (-40, True) and a.saturate(10, 0) == (10, False)
    assert a.electrical_power(10, 2) == pytest.approx(40) and a.electrical_power(10, -2) == 0
    with pytest.raises(ActuatorError):
        Actuator(efficiency=1.5).validate()


def test_zero_gain_and_zero_added_mass_identities():
    p = ex.default_params()
    p.exo.gain = 0.0
    p.exo.added_masses_kg = [0, 0, 0]
    r = ex.run(p)["A"]
    assert np.allclose(r["tau_loaded"], r["tau_baseline"]) and np.allclose(r["tau_human"], r["tau_baseline"])
    assert np.all(r["tau_exo"] == 0) and r["summary"]["actuator_electrical_energy_j"] == 0


def test_added_mass_increases_required_torque():
    p = ex.default_params()
    p.exo.gain = 0.0
    s = ex.run(p)["A"]["summary"]
    assert s["loaded_peak_torque_nm"] > s["baseline_peak_torque_nm"]


def test_full_gain_unlimited_actuator_cancels_joint_torque():
    p = ex.default_params()
    p.exo.gain = 1.0
    p.exo.actuator = Actuator(tau_stall_nm=1e6, omega_noload_rad_s=1e6)
    r = ex.run(p)["A"]
    j = p.exo.joint_index
    assert np.allclose(r["tau_human"][:, j], 0, atol=1e-9) and r["summary"]["saturation_fraction"] == 0
    other = [k for k in range(3) if k != j]
    assert np.allclose(r["tau_human"][:, other], r["tau_loaded"][:, other])  # outras juntas não mudam


def test_saturation_respects_curve_and_warns():
    p = ex.default_params()
    p.exo.gain = 1.0
    p.exo.actuator = Actuator(tau_stall_nm=3.0, omega_noload_rad_s=2.0)
    res = ex.run(p)
    r = res["A"]
    assert np.all(np.abs(r["tau_exo"]) <= r["tau_limit"] + 1e-12) and r["saturated"].any()
    assert any("saturou" in m for m in res["messages"])
    assert r["summary"]["human_peak_torque_nm"] > 0


def test_gravity_mode_and_monotonic_assistance():
    p = ex.default_params()
    p.exo.mode = "gravity"
    peaks = []
    for g in (0.0, 0.5, 1.0):
        p.exo.gain = g
        peaks.append(ex.run(p)["A"]["summary"]["actuator_peak_torque_nm"])
    assert peaks[0] == 0 and peaks[1] < peaks[2]


def test_validation():
    p = ex.default_params()
    p.exo.mode = "magia"
    with pytest.raises(ex.ExoError):
        ex.run(p)
    p = ex.default_params()
    p.exo.joint_index = 9
    with pytest.raises(ex.ExoError):
        ex.run(p)
    p = ex.default_params()
    p.exo.added_masses_kg = [1, 1]
    with pytest.raises(ex.ExoError):
        ex.run(p)


def test_csv_report_project_reproducible(tmp_path):
    import csv
    p = ex.default_params()
    r1 = ex.run(p)
    r2 = ex.run(ex.Exo001Params.from_dict(json.loads(json.dumps(p.to_dict()))))
    assert np.array_equal(r1["A"]["tau_human"], r2["A"]["tau_human"])
    f = tmp_path / "e.csv"
    ex.export_csv(r1, f)
    rows = list(csv.reader(open(f, encoding="utf-8")))
    assert len(rows) == 1 + p.samples and rows[0][6] == "tau_human_Nm"
    md = ex.report_markdown(r1)
    for s in ("Parâmetros de entrada", "Hipóteses", "Método", "Limitações", "DEMONSTRATIVO", "Energia elétrica"):
        assert s in md
    pm = ProjectManager()
    pm.create(tmp_path / "p", "P")
    pm.add_experiment(ex.EXPERIMENT_ID, p.to_dict(), ex.summary_dict(r1), lambda path: ex.export_csv(r1, path))
    pm.save(); pm.close(); pm.open(tmp_path / "p")
    again = ex.run(ex.Exo001Params.from_dict(pm.data["experiments"][0]["params"]))
    assert ex.summary_dict(again) == json.loads(json.dumps(pm.data["experiments"][0]["summary"]))

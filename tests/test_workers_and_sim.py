import math

import numpy as np
import pytest

from core.exceptions import SimulationCancelled
from infrastructure.workers.worker import TaskThread
from research.experiments import bio001, passive_sim as ps
from research.reports.pdf_report import export_pdf


def test_passive_sim_energy_and_determinism():
    p = ps.PassiveParams(t_end_s=1.5)
    r1, r2 = ps.run(p), ps.run(ps.PassiveParams.from_dict(p.to_dict()))
    assert r1["A"]["summary"]["max_rel_energy_drift"] < 1e-6
    assert np.array_equal(r1["A"]["q"], r2["A"]["q"])
    assert len(r1["A"]["t"]) <= 1001
    assert r1["A"]["summary"]["steps"] == 1500


def test_passive_sim_hanging_equilibrium_stays():
    p = ps.PassiveParams(q1_deg=-90, q2_deg=0, t_end_s=1.0)
    r = ps.run(p)
    assert np.allclose(r["A"]["q"][:, 0], -math.pi / 2, atol=1e-9)
    assert np.allclose(r["A"]["q"][:, 1], 0, atol=1e-9)


def test_passive_sim_validation():
    with pytest.raises(ps.SimError):
        ps.run(ps.PassiveParams(dt_s=0.05))
    with pytest.raises(ps.SimError):
        ps.run(ps.PassiveParams(m1=0))
    with pytest.raises(ps.SimError):
        ps.run(ps.PassiveParams(t_end_s=1e5, dt_s=1e-3))


def test_cancel_callback_raises():
    with pytest.raises(SimulationCancelled):
        ps.run(ps.PassiveParams(), should_cancel=lambda: True)


def test_worker_success_progress_and_cancel(qtbot):
    prog = []
    th = TaskThread(lambda progress, cancelled: ps.run(ps.PassiveParams(t_end_s=2.0), progress, cancelled))
    th.progress.connect(prog.append)
    with qtbot.waitSignal(th.succeeded, timeout=30000) as sig:
        th.start()
    th.wait()
    assert sig.args[0]["id"] == "SIM-001" and prog and prog[-1] <= 100 and max(prog) > 0

    th2 = TaskThread(lambda progress, cancelled: ps.run(ps.PassiveParams(t_end_s=60.0), progress, cancelled))
    th2.progress.connect(lambda v: th2.cancel())
    with qtbot.waitSignal(th2.cancelled, timeout=30000):
        th2.start()
    th2.wait()


def test_worker_failure_reported(qtbot):
    def boom(progress, cancelled):
        raise ValueError("falhou")
    th = TaskThread(boom)
    with qtbot.waitSignal(th.failed, timeout=10000) as sig:
        th.start()
    th.wait()
    assert "falhou" in sig.args[0]


def test_pdf_report(tmp_path):
    f = tmp_path / "r.pdf"
    export_pdf(bio001.run(bio001.default_params()), f)
    data = f.read_bytes()
    assert data.startswith(b"%PDF") and data.count(b"/Type /Page\n") + data.count(b"/Type /Page ") >= 2
    assert not (tmp_path / "r.pdf.tmp").exists()

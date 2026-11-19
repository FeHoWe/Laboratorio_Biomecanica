import numpy as np
import pyvista as pv
import pytest

from biomechanics.human_model.lower_limb import LowerLimbModel
from visualization.viewport_3d.scene import LimbScene, cylinder_between


@pytest.fixture
def plotter():
    pl = pv.Plotter(off_screen=True, window_size=(480, 360))
    yield pl
    pl.close()


def test_cylinder_geometry():
    c = cylinder_between((0, 0, 0), (0, 2, 0), 0.1)
    b = c.bounds
    assert b[3] == pytest.approx(2.0, abs=1e-6) and b[2] == pytest.approx(0.0, abs=1e-6)
    with pytest.raises(ValueError):
        cylinder_between((0, 0, 0), (0, 0, 0), 0.1)


def test_scene_builds_updates_and_renders(plotter, tmp_path):
    m = LowerLimbModel()
    sc = LimbScene(plotter)
    sc.set_model(m)
    assert set(sc.actors) == {"pelvis", "femur", "tibia", "fibula", "foot"}
    top0 = np.array(sc.meshes["foot"].center)
    m.set_angle("ankle", 25)
    m.set_angle("knee", 70)
    sc.update()
    assert not np.allclose(np.array(sc.meshes["foot"].center), top0)  # a malha segue a cinemática
    ep = m.segment_endpoints()["tibia"]
    assert np.allclose(np.array(sc.meshes["tibia"].center), (ep[0] + ep[1]) / 2, atol=1e-6)
    sc.select("femur")
    assert sc.actors["femur"].prop.color.hex_rgb.lower() == "#f5a623"
    assert sc.name_for_actor(sc.actors["tibia"]) == "tibia"
    img = tmp_path / "s.png"
    plotter.screenshot(str(img))
    assert img.stat().st_size > 3000


def test_viewport_widget_falls_back_without_gl(qtbot):
    from interface.widgets.viewport3d import Viewport3D
    v = Viewport3D()  # plataforma offscreen -> sem contexto GL
    qtbot.addWidget(v)
    assert v.available is False
    v.set_model(LowerLimbModel())  # não deve falhar
    v.refresh()

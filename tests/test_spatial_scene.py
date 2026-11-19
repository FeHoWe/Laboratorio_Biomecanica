"""ETAPA 4 — visualização 3D dinâmica: controlador de reprodução (puro) e cena VTK offscreen (transformações, não recriação)."""
import numpy as np
import pytest
import pyvista as pv

from biomechanics.human_model.spatial_lower_limb import build_spatial_lower_limb
from biomechanics.spatial import transforms as T
from visualization.viewport_3d.playback import PlaybackController, PlaybackError
from visualization.viewport_3d.spatial_scene import CAMERA_PRESETS, SpatialScene, vector_arrow


def test_playback_controller_logic():
    t = np.linspace(0, 2.0, 201)
    pc = PlaybackController(t)
    assert pc.index == 0 and not pc.playing and pc.advance(1.0) == 0   # parado: não avança
    pc.play(); pc.set_speed(2.0)
    assert pc.advance(0.5) == 100 and np.isclose(pc.time, 1.0)          # 2× · 0,5 s = 1,0 s simulado
    pc.pause(); assert pc.advance(10) == 100
    pc.play(); pc.advance(10)
    assert pc.finished and not pc.playing and pc.index == 200
    pc.play(); assert pc.time == 0.0 and pc.playing                       # play após o fim reinicia
    pc.restart(); assert pc.index == 0
    assert pc.seek(5.0) == 200 and pc.seek(-1) == 0 and pc.seek(1.004) in (100, 101)
    pc.loop = True; pc.play(); pc.set_speed(1.0); pc.advance(2.5)
    assert pc.playing and 0 <= pc.time < 2.0
    for bad in (lambda: pc.set_speed(0), lambda: pc.advance(-1), lambda: PlaybackController([0.0]), lambda: PlaybackController([0, 1, 1])):
        with pytest.raises(PlaybackError):
            bad()


def test_vector_arrow_geometry():
    assert vector_arrow([0, 0, 0], [0, 0, 0]) is None
    a = vector_arrow([1, 2, 3], [0, 2.0, 0], 0.5)
    assert np.isclose(a.bounds[3] - a.bounds[2], 1.0, atol=1e-6) and np.isclose(a.bounds[2], 2.0, atol=1e-6)


@pytest.fixture
def plotter():
    pl = pv.Plotter(off_screen=True, window_size=(480, 360))
    yield pl
    pl.close()


def test_scene_updates_transforms_without_recreating_actors(plotter, tmp_path):
    ch = build_spatial_lower_limb()
    sc = SpatialScene(plotter)
    sc.set_chain(ch)
    assert set(sc.actors) == {"pelvis", "femur", "tibia", "fibula", "foot"}
    created = sc.n_actor_creations
    ids = {k: id(v) for k, v in sc.actors.items()}
    q = np.radians([30, 10, 5, 50, -8, 4])
    sc.update(q)
    fk = ch.forward_kinematics(q)
    for bid in sc.actors:
        assert np.allclose(np.array(sc.actors[bid].user_matrix), fk.T[bid], atol=1e-12)    # ator segue exatamente a FK
        assert np.allclose(np.array(sc.axis_actors[bid][0].user_matrix), fk.T[bid], atol=1e-12)
        assert np.allclose(np.array(sc.com_actors[bid].user_matrix), fk.T[bid], atol=1e-12)
    assert np.allclose(np.array(sc.joint_actors["joelho"].user_matrix)[:3, 3], fk.T["tibia"][:3, 3], atol=1e-12)
    assert np.allclose(np.array(sc.total_com_actor.user_matrix)[:3, 3], ch.total_com(q), atol=1e-12)
    for _ in range(5):
        sc.update(q * np.random.default_rng(0).uniform(0, 1))
    assert sc.n_actor_creations == created and ids == {k: id(v) for k, v in sc.actors.items()}   # nenhum ator recriado
    sc.update(q)   # o laço acima deixou outra pose; volta à pose q antes de comparar
    # a geometria transformada do pé está onde a FK diz
    foot_tip = T.apply(fk.T["foot"], [ch.bodies["foot"].length_m, 0, 0])
    assert np.allclose(foot_tip, T.apply(np.array(sc.actors["foot"].user_matrix), [ch.bodies["foot"].length_m, 0, 0]), atol=1e-12)
    img = tmp_path / "s.png"
    plotter.screenshot(str(img))
    assert img.stat().st_size > 3000


def test_scene_vectors_trajectory_selection_visibility_and_cameras(plotter):
    ch = build_spatial_lower_limb()
    sc = SpatialScene(plotter)
    sc.set_chain(ch)
    n = sc.set_vectors([([0, 1, 0], [0, 10.0, 0], 0.01, "#ff9f43"), ([0, 1, 0], [0, 0, 0], 0.01, "#ff9f43")], "tau")
    assert n == 1                                    # vetor nulo não é desenhado (nada inventado)
    sc.set_trajectory([[0, 0, 0], [0.1, 0.1, 0], [0.2, 0.0, 0.1]])
    sc.clear_trajectory()
    sc.select("tibia")
    assert sc.actors["tibia"].prop.color.hex_rgb.lower() == "#f5a623" and sc.selected == "tibia"
    assert sc.body_for_actor(sc.actors["foot"]) == "foot" and sc.body_for_actor(object()) is None
    sc.set_visibility(axes=False, com=False)
    assert not sc.axis_actors["femur"][0].GetVisibility() and not sc.com_actors["femur"].GetVisibility()
    sc.set_visibility(axes=True, com=True)
    assert sc.axis_actors["femur"][0].GetVisibility()
    for preset in CAMERA_PRESETS:
        sc.camera(preset)
        pos = np.array(plotter.camera_position[0])
        assert np.allclose(pos, CAMERA_PRESETS[preset][0], atol=1e-6)
    with pytest.raises(KeyError):
        sc.camera("inexistente")

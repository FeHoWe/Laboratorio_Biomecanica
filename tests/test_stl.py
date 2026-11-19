import struct

import numpy as np
import pytest

from core.geometry.stl import StlError, StlMesh, load_stl, write_binary_stl


def cube(s=2.0):
    v = np.array([[x, y, z] for x in (0, s) for y in (0, s) for z in (0, s)], float)
    f = [(0, 2, 3), (0, 3, 1), (4, 5, 7), (4, 7, 6), (0, 1, 5), (0, 5, 4), (2, 6, 7), (2, 7, 3), (0, 4, 6), (0, 6, 2), (1, 3, 7), (1, 7, 5)]
    return StlMesh(v, np.array(f))


def test_binary_roundtrip_stats(tmp_path):
    p = tmp_path / "c.stl"
    write_binary_stl(cube(2.0), p)
    m = load_stl(p)
    s = m.stats()
    assert s["triangles"] == 12 and s["vertices"] == 8 and s["closed"]
    assert s["area"] == pytest.approx(24.0) and s["volume"] == pytest.approx(8.0)
    assert s["bounds_min"] == [0, 0, 0] and s["bounds_max"] == [2, 2, 2]
    assert m.scaled(0.001).volume() == pytest.approx(8e-9)


def test_ascii_and_open_mesh_has_no_volume(tmp_path):
    p = tmp_path / "t.stl"
    p.write_text("solid t\nfacet normal 0 0 1\nouter loop\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid t\n")
    m = load_stl(p)
    assert m.n_triangles == 1 and not m.is_closed() and m.volume() is None and m.area() == pytest.approx(0.5)


@pytest.mark.parametrize("content", [b"", b"abc", b"x" * 200, b"solid x\nvertex 1 2\n"])
def test_invalid_files(tmp_path, content):
    p = tmp_path / "bad.stl"
    p.write_bytes(content)
    with pytest.raises(StlError):
        load_stl(p)


def test_binary_size_mismatch_nan_and_degenerate(tmp_path):
    p = tmp_path / "c.stl"
    write_binary_stl(cube(), p)
    raw = p.read_bytes()
    (tmp_path / "trunc.stl").write_bytes(raw[:-10])
    with pytest.raises(StlError):
        load_stl(tmp_path / "trunc.stl")
    nanv = bytearray(raw)
    nanv[96:100] = struct.pack("<f", float("nan"))
    (tmp_path / "nan.stl").write_bytes(bytes(nanv))
    with pytest.raises(StlError, match="não finitas"):
        load_stl(tmp_path / "nan.stl")
    deg = StlMesh(np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], float), np.array([[0, 1, 2]]))
    zero = StlMesh(np.zeros((3, 3)), np.array([[0, 1, 2]]))
    write_binary_stl(zero, tmp_path / "z.stl")
    with pytest.raises(StlError, match="degenerados"):
        load_stl(tmp_path / "z.stl")
    write_binary_stl(deg, tmp_path / "ok.stl")
    assert load_stl(tmp_path / "ok.stl").n_triangles == 1


def test_missing_file(tmp_path):
    with pytest.raises(StlError):
        load_stl(tmp_path / "nao_existe.stl")


def test_import_into_project_and_scene_builder(tmp_path):
    import json
    import shutil as sh
    from application.project_manager import ProjectManager
    from core.exceptions import ProjectValidationError
    from visualization.viewport_3d.scene import mesh_polydata
    src = tmp_path / "meu osso.stl"
    write_binary_stl(cube(100.0), src)  # 100 mm
    pm = ProjectManager()
    pm.create(tmp_path / "p", "P")
    idx = pm.import_stl(src, "mm")
    m = pm.data["models"][idx]
    assert m["type"] == "stl_mesh" and (tmp_path / "p" / m["file"]).is_file() and m["scale_to_m"] == 0.001
    assert m["stats_m"]["volume"] == pytest.approx(1e-3) and m["stats_m"]["closed"]
    idx2 = pm.import_stl(src, "cm")  # mesmo nome: não sobrescreve
    assert pm.data["models"][idx2]["file"] != m["file"] and (tmp_path / "p" / m["file"]).is_file()
    with pytest.raises(ProjectValidationError):
        pm.import_stl(src, "furlong")
    bad = tmp_path / "bad.stl"
    bad.write_bytes(b"lixo" * 50)
    n_models = len(pm.data["models"])
    with pytest.raises(StlError):
        pm.import_stl(bad)
    assert len(pm.data["models"]) == n_models and not list((tmp_path / "p" / "models").glob("bad*"))
    pm.save(); pm.close(); pm.open(tmp_path / "p")  # persiste e reabre
    assert pm.data["models"][idx]["stats_m"]["triangles"] == 12
    pd = mesh_polydata(*(lambda mm: (mm.vertices, mm.faces))(load_stl(tmp_path / "p" / m["file"]).scaled(0.001)))
    assert pd.n_cells == 12 and pd.n_points == 8

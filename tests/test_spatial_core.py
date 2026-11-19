"""ETAPA 1 — testes matemáticos do núcleo espacial (rotações, quaternions, referenciais, corpos rígidos, juntas)."""
import numpy as np
import pytest

from biomechanics.spatial import quaternions as Q
from biomechanics.spatial import rotations as R
from biomechanics.spatial import transforms as T
from biomechanics.spatial.coordinate_frames import FrameError, FrameTree
from biomechanics.spatial.rigid_body import RigidBody, RigidBodyError, cylinder_inertia, parallel_axis
from biomechanics.spatial.spatial_joints import JointError, SpatialJoint, fixed, prismatic, revolute, spherical

RNG = np.random.default_rng(12345)  # semente fixa: testes determinísticos


def rand_rotations(n=50):
    for _ in range(n):
        yield R.axis_angle_matrix(RNG.normal(size=3), RNG.uniform(-np.pi, np.pi))


# ---------------- rotações ----------------
def test_rodrigues_matches_elementary_rotations_and_known_case():
    a = 0.7
    assert np.allclose(R.axis_angle_matrix([0, 0, 1], a), T.rot_z(a))
    assert np.allclose(R.axis_angle_matrix([1, 0, 0], a), T.rot_x(a))
    assert np.allclose(R.axis_angle_matrix([0, 5, 0], a), T.rot_y(a))  # eixo é normalizado
    assert np.allclose(R.axis_angle_matrix([0, 0, 1], np.pi / 2) @ [1, 0, 0], [0, 1, 0])


def test_so3_properties_orthogonality_det_composition():
    Rs = list(rand_rotations())
    for M in Rs:
        assert np.allclose(M @ M.T, np.eye(3), atol=1e-12) and np.isclose(np.linalg.det(M), 1.0, atol=1e-12)
    for A, B in zip(Rs[:-1], Rs[1:]):
        C = A @ B
        assert R.is_rotation(C, 1e-12) and np.allclose(np.linalg.inv(A), A.T, atol=1e-12)
    with pytest.raises(R.RotationError):
        R.axis_angle_matrix([0, 0, 0], 1.0)
    assert not R.is_rotation(np.diag([1, 1, -1.0]))  # reflexão: det = −1


def test_matrix_log_roundtrip_including_near_pi_and_zero():
    for M in rand_rotations():
        ax, ang = R.matrix_log(M)
        assert 0 <= ang <= np.pi + 1e-12 and np.allclose(R.axis_angle_matrix(ax, ang), M, atol=1e-9)
    ax, ang = R.matrix_log(R.axis_angle_matrix([1, 2, 3], np.pi))
    assert np.isclose(ang, np.pi) and np.allclose(abs(ax @ unit3([1, 2, 3])), 1.0)
    assert R.matrix_log(np.eye(3))[1] == 0.0
    with pytest.raises(R.RotationError):
        R.matrix_log(np.diag([2.0, 1, 1]))


def unit3(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def test_euler_zxy_roundtrip_and_gimbal_lock():
    for _ in range(100):
        a, c = RNG.uniform(-np.pi, np.pi, 2)
        b = RNG.uniform(-1.4, 1.4)
        M = R.euler_zxy_to_matrix(a, b, c)
        a2, b2, c2, lock = R.matrix_to_euler_zxy(M)
        assert not lock and np.allclose([a, b, c], [a2, b2, c2], atol=1e-9)
    M = R.euler_zxy_to_matrix(0.3, np.pi / 2, 0.5)
    a2, b2, c2, lock = R.matrix_to_euler_zxy(M)
    assert lock and np.allclose(R.euler_zxy_to_matrix(a2, b2, c2), M, atol=1e-9)  # ainda reconstrói a rotação


def test_orthonormalize_repairs_drift():
    M = next(rand_rotations(1))
    noisy = M + 1e-4 * RNG.normal(size=(3, 3))
    fixed_ = R.orthonormalize(noisy)
    assert R.is_rotation(fixed_, 1e-12) and np.linalg.norm(fixed_ - M) < 1e-3


# ---------------- quaternions ----------------
def test_quaternion_matrix_roundtrip_and_double_cover():
    for M in rand_rotations():
        q = Q.from_matrix(M)
        assert np.isclose(np.linalg.norm(q), 1.0) and q[0] >= 0
        assert np.allclose(Q.to_matrix(q), M, atol=1e-12) and np.allclose(Q.to_matrix(-q), M, atol=1e-12)


def test_quaternion_from_matrix_all_branches_near_180():
    for axis in ([1, 0, 0], [0, 1, 0], [0, 0, 1], [1, 1, 1]):
        M = R.axis_angle_matrix(axis, np.pi - 1e-7)
        assert np.allclose(Q.to_matrix(Q.from_matrix(M)), M, atol=1e-9)


def test_quaternion_product_rotate_normalization_inverse():
    for A, B in zip(list(rand_rotations(20))[:-1], list(rand_rotations(20))[1:]):
        qa, qb = Q.from_matrix(A), Q.from_matrix(B)
        assert np.allclose(Q.to_matrix(Q.multiply(qa, qb)), A @ B, atol=1e-12)
        v = RNG.normal(size=3)
        assert np.allclose(Q.rotate(qa, v), A @ v, atol=1e-12)
        assert np.allclose(Q.multiply(qa, Q.inverse(qa)), Q.identity(), atol=1e-12)
    assert np.isclose(np.linalg.norm(Q.normalize([2, 0, 0, 0])), 1.0)
    with pytest.raises(R.RotationError):
        Q.normalize([0, 0, 0, 0])


def test_axis_angle_slerp_and_angle_between():
    ax, ang = Q.to_axis_angle(Q.from_axis_angle([0, 1, 0], 1.2))
    assert np.allclose(ax, [0, 1, 0]) and np.isclose(ang, 1.2)
    p, q = Q.from_axis_angle([0, 0, 1], 0.0), Q.from_axis_angle([0, 0, 1], 1.0)
    mid = Q.slerp(p, q, 0.5)
    assert np.isclose(Q.angle_between(p, mid), 0.5) and np.isclose(Q.angle_between(mid, q), 0.5)
    assert np.isclose(Q.angle_between(q, -q), 0.0)  # q e −q são a mesma rotação
    assert np.isclose(np.linalg.norm(Q.slerp(p, q, 0.3)), 1.0)


# ---------------- transformações e referenciais ----------------
def test_transform_inverse_composition_and_apply():
    for M in rand_rotations(20):
        A = T.make(M, RNG.normal(size=3))
        assert T.is_transform(A) and np.allclose(A @ T.invert(A), np.eye(4), atol=1e-12)
    A = T.make(T.rot_z(np.pi / 2), [1, 0, 0])
    B = T.make(T.rot_x(0.4), [0, 2, 0])
    p = np.array([0.3, -0.2, 0.9])
    assert np.allclose(T.apply(T.compose(A, B), p), T.apply(A, T.apply(B, p)))
    assert np.allclose(T.apply(A, [1, 0, 0]), [1, 1, 0])
    assert np.allclose(T.apply_vector(A, [1, 0, 0]), [0, 1, 0])  # vetor livre: sem translação
    assert not T.is_transform(np.diag([1, 1, 1, 2.0]))


def test_rotation_about_point_keeps_point_fixed():
    pt = np.array([1.0, 2.0, 3.0])
    M = T.rotation_about([0, 0, 1], 0.9, pt)
    assert np.allclose(T.apply(M, pt), pt) and np.allclose(T.apply(M, pt + [1, 0, 0]), pt + [np.cos(0.9), np.sin(0.9), 0])


def test_frame_tree_conversions_and_errors():
    ft = FrameTree()
    ft.add("pelvis", "world", T.make(None, [0, 1, 0]))
    ft.add("femur", "pelvis", T.make(T.rot_z(np.pi / 2), [0, 0, 0]))
    assert np.allclose(ft.point([1, 0, 0], "femur", "pelvis"), [0, 1, 0])
    assert np.allclose(ft.point([1, 0, 0], "femur", "world"), [0, 2, 0])
    assert np.allclose(ft.vector([1, 0, 0], "femur", "world"), [0, 1, 0])
    assert np.allclose(ft.relative("femur", "femur"), np.eye(4))
    assert np.allclose(ft.relative("world", "femur") @ ft.relative("femur", "world"), np.eye(4), atol=1e-12)
    with pytest.raises(FrameError):
        ft.add("femur", "world", np.eye(4))
    with pytest.raises(FrameError):
        ft.add("x", "inexistente", np.eye(4))
    with pytest.raises(FrameError):
        ft.world("nada")


# ---------------- corpos rígidos ----------------
def make_body(**kw):
    d = dict(id="b", name="B", length_m=0.4, mass_kg=3.0, com_local_m=[0, -0.17, 0],
             inertia_kg_m2=cylinder_inertia(3.0, 0.4, 0.04).tolist())
    d.update(kw)
    return RigidBody(**d)


def test_cylinder_inertia_and_parallel_axis_analytic():
    m, L, r = 3.0, 0.4, 0.04
    I = cylinder_inertia(m, L, r, axis=1)
    assert np.isclose(I[1, 1], 0.5 * m * r * r) and np.isclose(I[0, 0], m * (3 * r * r + L * L) / 12)
    assert np.isclose(I[0, 0], I[2, 2])
    # haste fina (r→0) em torno da extremidade: m L²/3
    thin = parallel_axis(cylinder_inertia(m, L, 1e-9, axis=1), m, [0, L / 2, 0])
    assert np.isclose(thin[0, 0], m * L * L / 3, rtol=1e-6) and np.isclose(thin[1, 1], 0.0, atol=1e-9)


def test_rigid_body_validation_rules():
    make_body().validate()
    for bad in (dict(mass_kg=0.0), dict(length_m=-1.0), dict(com_local_m=[0, 0]),
                dict(inertia_kg_m2=[[1, 2, 0], [0, 1, 0], [0, 0, 1]]),            # assimétrico
                dict(inertia_kg_m2=np.diag([1, 1, -1.0]).tolist()),                 # não positivo
                dict(inertia_kg_m2=np.diag([10.0, 1, 1]).tolist()),                 # viola desigualdade triangular
                dict(reliability="CERTO"), dict(reliability="REFERENCIADO")):       # REFERENCIADO sem fonte
        with pytest.raises(RigidBodyError):
            make_body(**bad).validate()
    make_body(reliability="REFERENCIADO", source="Autor, Ano, tabela X").validate()


def test_rigid_body_dict_roundtrip():
    b = make_body(visual={"shape": "cylinder", "radius_m": 0.04, "p0": [0, 0, 0], "p1": [0, -0.4, 0]})
    b2 = RigidBody.from_dict(b.to_dict())
    assert b2.to_dict() == b.to_dict() and b2.reliability == "DEMONSTRATIVO"
    with pytest.raises(RigidBodyError):
        RigidBody.from_dict({"id": "x"})


# ---------------- juntas ----------------
def test_revolute_prismatic_fixed_transforms():
    j = revolute("knee", "femur", "tibia", [0, 0, -1], [0, -0.4, 0], (0, 2.4))
    assert np.allclose(j.transform([0.0]), T.make(None, [0, -0.4, 0]))
    M = j.transform([0.5])
    assert np.allclose(M[:3, :3], T.rot_z(-0.5)) and np.allclose(M[:3, 3], [0, -0.4, 0])  # axis −z, ângulo +
    p = prismatic("slide", "a", "b", [1, 0, 0], [0, 0, 0], (0, 0.3))
    assert np.allclose(p.transform([0.2])[:3, 3], [0.2, 0, 0])
    f = fixed("weld", "a", "b", [0, 0, 0.05])
    assert f.n_dof == 0 and np.allclose(f.transform([]), T.make(None, [0, 0, 0.05]))


def test_spherical_equals_intrinsic_euler_product_and_gimbal_margin():
    h = spherical("hip", "pelvis", "femur", [0, 0, 0])
    q = [0.4, -0.3, 0.2]
    assert np.allclose(h.transform(q)[:3, :3], R.euler_zxy_to_matrix(*q))
    assert np.isclose(h.gimbal_margin(q), np.cos(-0.3)) and np.isclose(h.gimbal_margin([0, np.pi / 2, 0]), 0.0, atol=1e-12)
    assert revolute("r", "a", "b", [0, 0, 1], [0, 0, 0]).gimbal_margin([0.1]) is None


def test_joint_limits_and_construction_errors():
    j = revolute("r", "a", "b", [0, 0, 1], [0, 0, 0], (-0.5, 0.5))
    assert j.violations([0.4]) == [] and len(j.violations([0.6])) == 1
    for build in (lambda: revolute("r", "a", "a", [0, 0, 1], [0, 0, 0]),                      # pai = filho
                  lambda: revolute("r", "a", "b", [0, 0, 0], [0, 0, 0]),                      # eixo nulo
                  lambda: revolute("r", "a", "b", [0, 0, 1], [0, 0, 0], (1.0, 0.0)),          # min >= max
                  lambda: spherical("s", "a", "b", [0, 0, 0], axes=((0, 0, 1), (0, 0, 1), (0, 1, 0)))):  # eixos paralelos
        with pytest.raises(JointError):
            build()
    with pytest.raises(JointError):
        j.transform([0.1, 0.2])
    with pytest.raises(JointError):
        SpatialJoint.from_dict({"name": "x"})


def test_joint_dict_roundtrip():
    h = spherical("hip", "pelvis", "femur", [0, -0.1, 0.05], limits_rad=[(-0.3, 2.0), (-0.8, 0.8), (-0.9, 0.9)])
    h2 = SpatialJoint.from_dict(h.to_dict())
    q = [0.2, 0.1, -0.3]
    assert np.allclose(h2.transform(q), h.transform(q)) and h2.to_dict() == h.to_dict()

import math

import numpy as np
import pytest

from biomechanics.human_model.lower_limb import (ANKLE_HEIGHT, JointLimitError, LowerLimbModel, ModelError)


def test_neutral_pose_standing():
    m = LowerLimbModel()
    fk = m.forward_kinematics()
    s = m.segments
    assert np.allclose(fk["hip"], [0, s["femur"].length_m + s["tibia"].length_m + ANKLE_HEIGHT, 0])
    assert np.allclose(fk["knee"][[0, 2]], 0) and np.allclose(fk["ankle"][[0, 2]], 0)
    assert fk["ankle"][1] == pytest.approx(ANKLE_HEIGHT)           # tornozelo a ANKLE_HEIGHT do solo
    assert np.allclose(fk["toe"], [s["foot"].length_m, ANKLE_HEIGHT, 0])  # pé aponta para frente


def test_hip_flexion_90_thigh_horizontal_forward():
    m = LowerLimbModel()
    m.set_angle("hip", 90)
    fk = m.forward_kinematics()
    assert np.allclose(fk["knee"] - fk["hip"], [m.segments["femur"].length_m, 0, 0], atol=1e-12)


def test_knee_flexion_moves_shank_backward():
    m = LowerLimbModel()
    m.set_angle("knee", 90)
    fk = m.forward_kinematics()
    shank = fk["ankle"] - fk["knee"]
    assert shank[0] == pytest.approx(-m.segments["tibia"].length_m) and shank[1] == pytest.approx(0, abs=1e-12)


def test_ankle_dorsiflexion_lifts_toes():
    m = LowerLimbModel()
    m.set_angle("ankle", 30)
    toe_up = m.forward_kinematics()["toe"][1]
    m.set_angle("ankle", -30)
    toe_down = m.forward_kinematics()["toe"][1]
    assert toe_up > ANKLE_HEIGHT > toe_down


def test_segment_lengths_preserved_for_any_pose():
    m = LowerLimbModel()
    rng = np.random.default_rng(1)
    for _ in range(30):
        for j, jd in m.joints.items():
            m.set_angle(j, rng.uniform(jd.min_deg, jd.max_deg))
        ep = m.segment_endpoints()
        for name in ("femur", "tibia", "foot"):
            p0, p1 = ep[name]
            assert np.linalg.norm(p1 - p0) == pytest.approx(m.segments[name].length_m, rel=1e-12)


def test_joint_limits_enforced_and_clamp():
    m = LowerLimbModel()
    with pytest.raises(JointLimitError):
        m.set_angle("knee", -5)
    with pytest.raises(JointLimitError):
        m.set_angle("hip", float("nan"))
    assert m.set_angle("knee", 500, clamp=True) == 140
    assert m.angles_deg["knee"] == 140
    with pytest.raises(ModelError):
        m.set_angle("shoulder", 0)
    assert m.angles_deg["knee"] == 140  # estado preservado após erro


def test_limits_configurable_and_validated():
    m = LowerLimbModel()
    m.joints["knee"].max_deg = 100
    with pytest.raises(JointLimitError):
        m.set_angle("knee", 120)
    m.joints["knee"].min_deg = 200
    with pytest.raises(ModelError):
        m.validate()


def test_total_com_between_segments_and_shifts_with_pose():
    m = LowerLimbModel()
    c0 = m.total_com()
    m.set_angle("hip", 60)
    c1 = m.total_com()
    assert c1[0] > c0[0] and c0[1] > ANKLE_HEIGHT
    assert c0[2] == pytest.approx(0)


def test_serialization_roundtrip_and_demo_flag():
    m = LowerLimbModel()
    m.set_angle("hip", 30)
    m2 = LowerLimbModel.from_dict(m.to_dict())
    assert m2.angles_deg == m.angles_deg and m2.to_dict() == m.to_dict()
    assert all("DEMONSTRATIVO" in s.source for s in m.segments.values())
    bad = m.to_dict()
    bad["segments"]["femur"]["length_m"] = 0
    with pytest.raises(ModelError):
        LowerLimbModel.from_dict(bad)

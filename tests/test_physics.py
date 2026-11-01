"""真实物理与失败对照，无需 OpenGL/网络。"""
from pathlib import Path
import tempfile
import unittest
import numpy as np
import mujoco

from chapters.week06.experiments import cube_drop, reset_step, urdf_experiment
from chapters.week07.grasp import make_env, run_task, summarize_hold


class PlatformPhysicsTest(unittest.TestCase):
    def test_reset_step_and_urdf_origin(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reset_step(root/"reset", render=False)
            urdf_experiment(root/"urdf", render=False)

    def test_gravity_and_collision(self):
        with tempfile.TemporaryDirectory() as directory:
            cube_drop(Path(directory), render=False)


class GraspPhysicsTest(unittest.TestCase):
    def test_brief_lift_does_not_count_as_stable_hold(self):
        records = [{"cube_xyz_m": [0, 0, .02], "tcp_xyz_m": [0, 0, .02], "bilateral": True, "cube_speed_m_s": 0.} for _ in range(50)]
        records[-1]["cube_xyz_m"] = [0, 0, .14]
        self.assertFalse(summarize_hold(records, .02)["stable_hold"])

    def test_object_has_free_dynamics(self):
        with make_env() as env:
            self.assertEqual(env.model.joint("cube_free").type[0], mujoco.mjtJoint.mjJNT_FREE)
            cube = env.model.body("cube").id
            # 只有同步两手指的 joint equality，没有物体 weld/mocap/绑定。
            self.assertFalse(env.model.body_mocapid[cube] >= 0)
            self.assertTrue(np.all(env.model.eq_type == mujoco.mjtEq.mjEQ_JOINT))

    def test_grasp_hold_release_and_open_fingers_negative_control(self):
        with tempfile.TemporaryDirectory() as directory:
            result = run_task("known", Path(directory)/"normal", render=False, release_check=True)
            self.assertTrue(result["success"])
            self.assertGreaterEqual(result["bilateral_contact_fraction"], .9)
            self.assertTrue(result["release_check"]["object_fell"])
            negative = run_task("known", Path(directory)/"open", render=False, close_gripper=False)
            self.assertFalse(negative["success"])
            self.assertFalse(negative["is_lifted"])

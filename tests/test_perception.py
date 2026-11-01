"""坐标链路、单位、无检测与轨迹速率；不照抄实现验证自洽。"""
import unittest
import numpy as np
from chapters.week06.scene import camera_xyaxes
from chapters.week07.perception import pixel_to_world, locate_red_cube
from chapters.week07.planner import LinearPlanner, PlannerConfig
from chapters.week07.controller import orientation_error


class GeometryTest(unittest.TestCase):
    def test_calibrated_world_point_with_known_answer(self):
        K = np.array([[200., 0, 100], [0, 200, 80], [0, 0, 1]])
        T = np.eye(4)
        T[:3, :3] = np.diag([1, -1, -1])
        T[:3, 3] = [1, 2, 3]
        np.testing.assert_allclose(pixel_to_world(120, 100, .5, K, T), [1.05, 1.95, 2.5])
        with self.assertRaises(ValueError):
            pixel_to_world(1, 1, 0, K, T)

    def test_orientation_error_does_not_vanish_at_180_degrees(self):
        error = orientation_error(np.eye(3), np.diag([1., -1., -1.]))
        self.assertAlmostEqual(np.linalg.norm(error), np.pi)

    def test_missing_target_raises(self):
        with self.assertRaisesRegex(ValueError, "not detected"):
            locate_red_cube(np.zeros((20,20,3)), np.ones((20,20)), {"K": np.eye(3), "T_world_camera_cv": np.eye(4)})

    def test_camera_degeneracy_and_top_down(self):
        with self.assertRaises(ValueError):
            camera_xyaxes([0, 0, 1], [0, 0, 1])
        self.assertEqual(len(camera_xyaxes([0, 0, 1], [0, 0, 0]).split()), 6)

    def test_trajectory_endpoint_and_speed_bound(self):
        config = PlannerConfig(.02, .08)
        start, target = np.array([.1, -.2, .3]), np.array([.5, .1, .2])
        trajectory = LinearPlanner(config).plan(start, target)
        np.testing.assert_allclose(trajectory[-1], target)
        steps = np.diff(np.vstack([start, trajectory]), axis=0)
        self.assertTrue(np.all(np.linalg.norm(steps, axis=1) <= config.speed*config.dt+1e-12))

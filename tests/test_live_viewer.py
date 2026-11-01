"""窗口关闭/参数校验无需图形设备；物理回归仍使用真实 MuJoCo。"""
from contextlib import nullcontext
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from chapters.week07.grasp import run_task, positive_speed
from chapters.week07.live_viewer import LiveViewer


class LiveViewerTest(unittest.TestCase):
    def test_speed_must_be_positive_finite(self):
        for speed in (0., -1., float("inf"), float("nan")):
            with self.assertRaises(ValueError):
                LiveViewer(None, speed=speed)
        self.assertEqual(positive_speed("0.5"), .5)

    def test_window_close_aborts_and_cleans_up_without_success(self):
        viewer = MagicMock()
        viewer.lock.return_value = nullcontext()
        viewer.is_running.return_value = False
        with tempfile.TemporaryDirectory() as directory:
            with patch("mujoco.viewer.launch_passive", return_value=viewer):
                result = run_task(output=Path(directory), render=False, human=True)
            self.assertEqual(result["status"], "aborted")
            self.assertFalse(result["success"])
            self.assertEqual(json.loads((Path(directory)/"result.json").read_text())["reason"], "viewer_closed")
            viewer.close.assert_called_once()

    def test_headless_never_launches_window(self):
        with patch("mujoco.viewer.launch_passive") as launch:
            with LiveViewer(None, enabled=False) as live:
                live.after_step()
                live.finish()
            launch.assert_not_called()

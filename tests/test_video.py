"""真实小尺寸MP4编解码验证，不需要OpenGL或外部ffmpeg安装。"""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import re
import subprocess
import unittest
import imageio_ffmpeg
import numpy as np

from chapters.week07.video import TaskVideo


class VideoTest(unittest.TestCase):
    def fake_env(self):
        return SimpleNamespace(data=SimpleNamespace(time=0.),
            render=lambda *args, **kwargs: np.full((64, 64, 3), 120, np.uint8))

    def read(self, path):
        decoded = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        fps = float(re.search(r"([0-9.]+) fps", decoded.stderr.decode()).group(1))
        return {"fps": fps}, len(decoded.stdout)//(64*64*3)

    def test_simulation_time_sampling_streams_valid_mp4(self):
        with tempfile.TemporaryDirectory() as directory:
            env = self.fake_env()
            with TaskVideo(directory, size=(64,64)) as video:
                for time in np.arange(0, .301, .02):
                    env.data.time = float(time)
                    video.capture(env)
            meta, frames = self.read(Path(directory)/"grasp.mp4")
            self.assertEqual(frames, 4)
            self.assertEqual(meta["fps"], 10)
            self.assertEqual(video.metadata()["status"], "completed")
            self.assertAlmostEqual(video.metadata()["last_frame_sim_time_s"], .3)
            self.assertIsNone(video.writer)
            self.assertFalse((Path(directory)/"grasp.partial.mp4").exists())

    def test_error_closes_encoder_and_preserves_playable_partial(self):
        with tempfile.TemporaryDirectory() as directory:
            env = self.fake_env()
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                with TaskVideo(directory, size=(64,64)) as video:
                    video.capture(env)
                    env.data.time = .1
                    video.capture(env)
                    raise RuntimeError("interrupted")
            self.assertEqual(video.metadata()["status"], "partial")
            self.assertIsNone(video.writer)
            self.assertFalse((Path(directory)/"grasp.mp4").exists())
            self.assertEqual(self.read(Path(directory)/"grasp.partial.mp4")[1], 2)

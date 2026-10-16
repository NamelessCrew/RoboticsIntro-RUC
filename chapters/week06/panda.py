"""Panda 有 9 个关节位置；默认控制器用 8 维动作协调 7 个臂关节和夹爪。"""
import numpy as np
from mani_skill.sensors.camera import CameraConfig
from mani_skill.utils import sapien_utils
from mani_skill.utils.registration import register_env
from .scene import SO100Env


@register_env("RUC-Panda-v1", max_episode_steps=100000)
class PandaBasicEnv(SO100Env):
    SUPPORTED_ROBOTS = ["panda"]
    QPOS_PRESETS = {
        "default": [0, np.pi / 8, 0, -5 * np.pi / 8, 0, 3 * np.pi / 4, np.pi / 4, 0.04, 0.04],
        "raised": [0, 0, 0, -np.pi / 2, 0, np.pi / 2, np.pi / 4, 0.04, 0.04],
    }
    CAMERA_PRESETS = {"default": ([1.2, -1.2, 1.0], [0.2, 0, 0.4]),
                      "side": ([0, -1.5, 0.8], [0.2, 0, 0.4]),
                      "oblique": ([1.1, -1.2, 1.3], [0.2, 0, 0.4])}

    def __init__(self, *args, robot_uids="panda", **kwargs):
        super().__init__(*args, robot_uids=robot_uids, **kwargs)

    @property
    def _default_human_render_camera_configs(self):
        eye, target = self.CAMERA_PRESETS["default"]
        return CameraConfig("render_camera", sapien_utils.look_at(eye, target), 512, 512,
                            np.pi / 2, 0.01, 100)

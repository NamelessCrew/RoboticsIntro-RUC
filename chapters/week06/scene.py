"""
SO100 机械臂仿真环境
用于加载和控制 SO100 5DOF 机械臂
"""
from typing import Dict
from pathlib import Path

import numpy as np
import sapien
import torch

from mani_skill.envs.sapien_env import BaseEnv
from mani_skill.sensors.camera import CameraConfig
from mani_skill.utils import sapien_utils
from mani_skill.utils.building.ground import build_ground
from mani_skill.utils.registration import register_env
from mani_skill.utils.structs.types import GPUMemoryConfig, SimConfig
from mani_skill.utils.building.actors import build_cube


@register_env("RUC-SO100-v1", max_episode_steps=100000)
class SO100Env(BaseEnv):
    """
    SO100 机械臂仿真环境
    
    这是一个用于 SO100 5DOF 机械臂的基础仿真环境，
    支持关节位置控制和夹爪控制。
    
    使用 ManiSkill 内置的 so100 机器人。
    """
    
    SUPPORTED_ROBOTS = ["so100", "so100_custom"]
    SUPPORTED_REWARD_MODES = ["none"]
    # 模型顺序：5 个机械臂关节 + 1 个夹爪关节，单位均为弧度。
    QPOS_PRESETS = {
        "default": [0, 0, 0, 0, 0, 0.6],
        "zero": [0, 0, 0, 0, 0, 0],
        "raised": [0.3, -0.8, 0.8, 0, 0.2, 0],
    }
    CAMERA_PRESETS = {
        "default": ([0.5, -0.5, 0.5], [0, 0, 0.15]),
        "side": ([0, -0.8, 0.4], [0, 0, 0]),  # 侧面视角：eye 与 target 一起调整
        "oblique": ([0.32, -0.44, 0.44], [0, -0.17, 0.17]),
    }
    
    def __init__(
        self, 
        *args, 
        robot_uids="so100",
        camera_preset="default",
        camera_eye=None,
        camera_target=None,
        sensor_resolution=(128, 128),
        camera_fov=np.pi / 2,
        ground_texture="default",
        lighting_preset="default",
        ambient_light=None,
        directional_light_direction=(1, 1, -1),
        initial_qpos_preset="default",
        initial_qpos=None,
        add_cube=False,
        cube_collision=True,
        **kwargs
    ):
        # 必须先保存配置，再调用父类：BaseEnv 构造时就会读取相机和场景参数。
        if camera_preset not in self.CAMERA_PRESETS:
            raise ValueError(f"Unknown camera preset: {camera_preset}")
        if initial_qpos_preset not in self.QPOS_PRESETS:
            raise ValueError(f"Unknown qpos preset: {initial_qpos_preset}")
        if lighting_preset not in ("default", "dark"):
            raise ValueError(f"Unknown lighting preset: {lighting_preset}")
        self._camera_preset = camera_preset
        eye, target = self.CAMERA_PRESETS[camera_preset]
        self._camera_eye = list(eye if camera_eye is None else camera_eye)
        self._camera_target = list(target if camera_target is None else camera_target)
        self._sensor_resolution = tuple(sensor_resolution)
        self._camera_fov = float(camera_fov)
        if len(self._sensor_resolution) != 2 or any(int(n) != n or n < 1 for n in self._sensor_resolution):
            raise ValueError("sensor_resolution must contain two positive integers")
        if not 0 < self._camera_fov < np.pi:
            raise ValueError("camera_fov must be in (0, pi) radians")
        self._ground_texture = ground_texture
        self._ambient_light = list(ambient_light if ambient_light is not None else
                                   ([0.08, 0.08, 0.12] if lighting_preset == "dark" else [0.3] * 3))
        self._light_direction = list(directional_light_direction)
        self._initial_qpos = np.asarray(self.QPOS_PRESETS[initial_qpos_preset]
                                        if initial_qpos is None else initial_qpos, dtype=np.float32)
        self._add_cube = add_cube
        self._cube_collision = cube_collision
        super().__init__(*args, robot_uids=robot_uids, **kwargs)
    
    @property
    def _default_sim_config(self):
        return SimConfig(
            spacing=20,
            gpu_memory_config=GPUMemoryConfig(
                max_rigid_contact_count=2**20,
                max_rigid_patch_count=2**19,
            )
        )
    
    @property
    def _default_sensor_configs(self):
        """配置默认相机传感器"""
        eye, target = self._get_camera_eye_target()
        direction = np.asarray(target) - np.asarray(eye)
        if direction.shape != (3,) or not np.isfinite(direction).all() or np.linalg.norm(direction) < 1e-6:
            raise ValueError("camera eye and target must be distinct finite 3D positions")
        # 俯视时选择不与视线平行的 up，避免相机姿态退化。
        up = [0, 1, 0] if np.linalg.norm(np.cross(direction, [0, 0, 1])) < 1e-6 else [0, 0, 1]
        pose = sapien_utils.look_at(eye, target, up=up)
        width, height = self._sensor_resolution
        return [CameraConfig("base_camera", pose, width, height, self._camera_fov, 0.01, 100)]

    def _get_camera_eye_target(self):
        return self._camera_eye, self._camera_target
    
    @property
    def _default_human_render_camera_configs(self):
        """配置用于人类观看的渲染相机"""
        pose = sapien_utils.look_at([0.6, -0.6, 0.6], [0.0, 0.0, 0.15])
        return CameraConfig("render_camera", pose, 1024, 1024, 1, 0.01, 100)
    
    def _load_agent(self, options: dict):
        """加载机器人代理"""
        super()._load_agent(options, sapien.Pose(p=[0, 0, 0]))
    
    def _load_scene(self, options: dict):
        """加载场景（地面等）"""
        if self._ground_texture == "default":
            self.ground = build_ground(self.scene)
        else:
            texture = self._ground_texture
            if texture == "checkerboard":
                texture = self._checkerboard_texture()
            if not Path(texture).is_file():
                raise FileNotFoundError(f"Ground texture does not exist: {texture}")
            self.ground = build_ground(self.scene, texture_file=str(texture))
        # 沿用 ManiSkill 地面碰撞组约定；纹理本身不改变摩擦系数。
        self.ground.set_collision_group_bit(group=2, bit_idx=30, bit=1)
        if self._add_cube:
            # half_size 是半边长，0.02 对应边长 4 cm。中心初始高度为 0.30 m。
            self.cube = build_cube(self.scene, half_size=0.02, color=[0.9, 0.2, 0.12, 1],
                                   name="course_cube", add_collision=self._cube_collision,
                                   initial_pose=sapien.Pose(p=[0.3, -0.2, 0.30]))

    @staticmethod
    def _checkerboard_texture():
        """仅首次生成 PNG；学生替换图片后再次运行时保留修改。"""
        from PIL import Image
        path = Path(__file__).resolve().parents[2] / ".cache/week06/checkerboard.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            return path
        yy, xx = np.indices((256, 256))
        gray = np.where((xx // 32 + yy // 32) % 2, 65, 225).astype(np.uint8)
        Image.fromarray(np.repeat(gray[..., None], 3, axis=2)).save(path)
        return path

    def _load_lighting(self, options: dict):
        """环境光改变整体亮度；物理参数和方向光保持相同。"""
        self.scene.set_ambient_light(self._ambient_light)
        self.scene.add_directional_light(self._light_direction, [1, 1, 1],
                                         shadow=self.enable_shadow, shadow_scale=5, shadow_map_size=2048)
        self.scene.add_directional_light([0, 0, -1], [1, 1, 1])
    
    def _initialize_episode(self, env_idx: torch.Tensor, options: dict):
        """初始化每个 episode"""
        qpos = np.asarray(options.get("initial_qpos", self._initial_qpos), dtype=np.float32)
        expected = self.agent.robot.get_qpos().shape[-1]
        if qpos.shape != (expected,) or not np.isfinite(qpos).all():
            raise ValueError(f"initial_qpos requires {expected} finite joint positions")
        limits = self.agent.robot.get_qlimits()[0].cpu().numpy()
        if np.any(qpos < limits[:, 0]) or np.any(qpos > limits[:, 1]):
            raise ValueError("initial_qpos exceeds model joint limits")
        # reset 同时恢复关节状态和控制器目标，避免沿用上一次的动作。
        self.agent.reset(qpos)
        if self._add_cube:
            # 状态顺序：位置(3)、四元数 wxyz(4)、线速度(3)、角速度(3)。
            # 重置位置之外也要清零速度，否则方块会带着上一次的速度重新下落。
            self.cube.set_state(torch.tensor([[0.3, -0.2, 0.30, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0]],
                                             device=self.device))
    
    def evaluate(self):
        """评估当前状态（用于奖励计算）"""
        return {}
    
    def _get_obs_extra(self, info: Dict):
        """获取额外的观测信息"""
        return dict()
    
    def get_joint_positions(self) -> np.ndarray:
        """获取当前关节位置"""
        return self.agent.robot.get_qpos().cpu().numpy()
    
    def get_joint_velocities(self) -> np.ndarray:
        """获取当前关节速度"""
        return self.agent.robot.get_qvel().cpu().numpy()
    
    def get_ee_pose(self):
        """获取末端执行器位姿"""
        return self.agent.tcp_pose

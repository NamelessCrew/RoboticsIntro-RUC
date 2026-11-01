"""单环境、CPU MuJoCo 教学接口。长度/深度为米，角度为弧度，时间为秒。"""
from pathlib import Path
import time
import xml.etree.ElementTree as ET

import mujoco
import numpy as np
from PIL import Image

from .robot import ROOT, SO100_JOINTS, PANDA_JOINTS, panda_mjcf, so100_mjcf


def numbers(values):
    return " ".join(str(float(x)) for x in values)


def camera_xyaxes(eye, target):
    eye, target = np.asarray(eye, float), np.asarray(target, float)
    if eye.shape != (3,) or target.shape != (3,) or not np.isfinite([eye, target]).all():
        raise ValueError("camera eye/target must be finite 3D vectors")
    z = eye - target  # MuJoCo 相机朝局部 -Z 看，局部 +Y 朝上。
    if np.linalg.norm(z) < 1e-8:
        raise ValueError("camera eye and target must differ")
    z /= np.linalg.norm(z)
    up = np.array([0., 1., 0.]) if abs(z[2]) > .999 else np.array([0., 0., 1.])
    x = np.cross(up, z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return numbers(np.r_[x, y])


class RobotEnv:
    QPOS_PRESETS = {
        "panda": {
            "default": [0, -.7854, 0, -2.3562, 0, 1.5708, .7854, .04, .04],
            "raised": [.3, -.6, .2, -1.8, 0, 1.5, .8, .025, .025],
        },
        "so100": {
            "default": [0, 0, 0, 0, 0, .6],
            "raised": [.3, -.8, .8, 0, .2, 0],
            "zero": [0]*6,
        },
    }
    sim_hz = 500
    control_hz = 50

    def __init__(self, robot="panda", urdf_path=None, camera_eye=None, camera_target=None,
                 sensor_resolution=(128, 128), camera_fov=np.pi/2,
                 human_eye=None, human_target=None, ground_texture="default",
                 lighting_preset="default", initial_qpos_preset="default", initial_qpos=None,
                 add_cube=False, cube_collision=True, cube_position=(.45, 0, .3),
                 gravity=(0, 0, -9.81), cube_friction=1.0):
        if robot not in self.QPOS_PRESETS:
            raise ValueError("robot must be panda or so100")
        if any(int(x) != x or x < 1 for x in sensor_resolution) or len(sensor_resolution) != 2:
            raise ValueError("sensor_resolution must be (width, height) positive integers")
        if not np.isfinite(camera_fov) or not 0 < camera_fov < np.pi:
            raise ValueError("camera_fov must be in (0, pi) radians")
        self.robot = robot
        self.joint_names = PANDA_JOINTS if robot == "panda" else SO100_JOINTS
        self.arm_dof = 7 if robot == "panda" else 5
        self.initial_qpos = np.array(initial_qpos if initial_qpos is not None else self.QPOS_PRESETS[robot][initial_qpos_preset], float)
        if self.initial_qpos.shape != (len(self.joint_names),) or not np.isfinite(self.initial_qpos).all():
            raise ValueError("initial_qpos shape/values do not match robot joints")
        self.camera_eye = list(camera_eye if camera_eye is not None else ([1, -1, .8] if robot == "panda" else [.5, -.5, .5]))
        self.camera_target = list(camera_target if camera_target is not None else ([.25, 0, .3] if robot == "panda" else [0, 0, .15]))
        self.sensor_resolution = tuple(map(int, sensor_resolution))
        self.camera_fov = float(camera_fov)
        self.ground_texture = str(ground_texture)
        self.add_cube = add_cube
        self.cube_position = np.asarray(cube_position, float)
        root = panda_mjcf() if robot == "panda" else so100_mjcf(urdf_path)
        option = root.find("option")
        if option is None:
            option = ET.SubElement(root, "option")
        option.set("timestep", str(1/self.sim_hz))
        option.set("gravity", numbers(gravity))
        option.set("integrator", "implicitfast")
        option.set("cone", "elliptic")
        option.set("iterations", "80")
        visual = root.find("visual")
        if visual is None:
            visual = ET.SubElement(root, "visual")
        ET.SubElement(visual, "global", offwidth=str(max(640, self.sensor_resolution[0])), offheight=str(max(512, self.sensor_resolution[1])))
        ET.SubElement(visual, "map", znear="0.001", zfar="10")
        ET.SubElement(visual, "headlight", active="0")
        world = root.find("worldbody")
        # 替换上游追踪灯，确保灯光实验只改变 ambient。
        for light in list(world.findall("light")):
            world.remove(light)
        ambient = ".08 .08 .12" if lighting_preset == "dark" else ".3 .3 .3"
        ET.SubElement(world, "light", name="key_light", pos="0 -1 2", dir="-.4 .6 -1", directional="true", ambient=ambient, diffuse=".65 .65 .65", specular=".1 .1 .1")
        ET.SubElement(world, "light", name="fill_light", pos="0 1 1", dir=".4 -.5 -.5", directional="true", diffuse=".35 .35 .35", ambient="0 0 0", castshadow="false")
        asset = root.find("asset")
        if asset is None:
            asset = ET.SubElement(root, "asset")
        if ground_texture == "default":
            ET.SubElement(asset, "texture", name="floor_texture", type="2d", builtin="checker", width="256", height="256", rgb1=".32 .34 .36", rgb2=".42 .44 .46")
        else:
            path = self._checkerboard_texture() if ground_texture == "checkerboard" else Path(ground_texture).resolve()
            if not path.is_file():
                raise FileNotFoundError(path)
            ET.SubElement(asset, "texture", name="floor_texture", type="2d", file=str(path))
        ET.SubElement(asset, "material", name="floor_material", texture="floor_texture", texrepeat="10 10", texuniform="true", reflectance=".05")
        ET.SubElement(world, "geom", name="floor", type="plane", size="2 2 .05", material="floor_material", friction="1 .005 .0001", condim="4")
        ET.SubElement(world, "camera", name="sensor", pos=numbers(self.camera_eye), xyaxes=camera_xyaxes(self.camera_eye, self.camera_target), fovy=str(np.degrees(self.camera_fov)))
        heye = human_eye if human_eye is not None else ([1.1, -.9, .85] if robot == "panda" else [.6, -.6, .6])
        htarget = human_target if human_target is not None else ([.25, 0, .3] if robot == "panda" else [0, 0, .15])
        ET.SubElement(world, "camera", name="demo", pos=numbers(heye), xyaxes=camera_xyaxes(heye, htarget), fovy="55")
        if add_cube:
            body = ET.SubElement(world, "body", name="cube", pos=numbers(cube_position))
            ET.SubElement(body, "freejoint", name="cube_free")
            ET.SubElement(body, "geom", name="cube_geom", type="box", size=".02 .02 .02", mass=".06", rgba=".85 .06 .04 1", friction=f"{cube_friction} .005 .0001", condim="4", contype="1" if cube_collision else "0", conaffinity="1" if cube_collision else "0", solref=".004 1")
        self.xml = ET.tostring(root, encoding="unicode")
        self.model = mujoco.MjModel.from_xml_string(self.xml)
        self.data = mujoco.MjData(self.model)
        self.joint_ids = np.array([self.model.joint(x).id for x in self.joint_names])
        self.qadr = self.model.jnt_qposadr[self.joint_ids]
        self.dadr = self.model.jnt_dofadr[self.joint_ids]
        self._renderers = {}
        self.reset()

    @staticmethod
    def _checkerboard_texture():
        path = Path(__file__).resolve().parents[2] / ".cache/week06/checkerboard.png"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            y, x = np.indices((256, 256))
            pixels = np.where(((x//32 + y//32) % 2)[..., None], [235, 210, 135], [65, 105, 145]).astype(np.uint8)
            Image.fromarray(pixels).save(path)
        return path

    @property
    def qpos(self):
        return self.data.qpos[self.qadr].copy()

    @property
    def cube_xyz(self):
        return self.data.body("cube").xpos.copy()

    @property
    def tcp_xyz(self):
        return self.data.site("tcp").xpos.copy()

    def reset(self, seed=0):
        """确定性重置。seed 为跨实验接口保留；当前场景没有随机项。"""
        mujoco.mj_resetData(self.model, self.data)
        self.data.qpos[self.qadr] = self.initial_qpos
        self.data.ctrl[:self.arm_dof] = self.initial_qpos[:self.arm_dof]
        self.data.ctrl[-1] = float(np.mean(self.initial_qpos[7:])/0.04*255) if self.robot == "panda" else self.initial_qpos[-1]
        mujoco.mj_forward(self.model, self.data)
        return self.state(), {"seed": seed}

    def step(self, action):
        """action: Panda 前7项绝对关节目标(rad)，末项夹爪0..255；SO100全6项rad。"""
        action = np.asarray(action, float)
        if action.shape != (self.model.nu,) or not np.isfinite(action).all():
            raise ValueError(f"Expected finite action shape {(self.model.nu,)}")
        limits = self.model.actuator_ctrlrange
        if np.any(action < limits[:, 0]-1e-7) or np.any(action > limits[:, 1]+1e-7):
            raise ValueError("action exceeds actuator ctrlrange")
        self.data.ctrl[:] = action
        mujoco.mj_step(self.model, self.data, nstep=self.sim_hz//self.control_hz)
        mujoco.mj_forward(self.model, self.data)
        if not np.isfinite(self.data.qpos).all():
            raise FloatingPointError("non-finite simulation state")
        return self.state(), 0., False, False, {}

    def state(self):
        return {"qpos": self.qpos, "qvel": self.data.qvel[self.dadr].copy(), "time": float(self.data.time)}

    def camera_params(self, name="sensor", resolution=None):
        width, height = resolution or self.sensor_resolution
        camera = self.model.camera(name)
        cid = camera.id
        f = height/(2*np.tan(np.radians(self.model.cam_fovy[cid])/2))
        K = np.array([[f, 0, (width-1)/2], [0, f, (height-1)/2], [0, 0, 1.]])
        # OpenCV: x右/y下/z前；MuJoCo: x右/y上/z后。
        R_world_cv = self.data.cam_xmat[cid].reshape(3, 3) @ np.diag([1., -1., -1.])
        T = np.eye(4)
        T[:3, :3], T[:3, 3] = R_world_cv, self.data.cam_xpos[cid]
        return {"K": K, "T_world_camera_cv": T, "depth_unit": "m", "depth_definition": "optical_axis_z", "pixel_centers": "integer, principal point=(size-1)/2"}

    def render(self, name="sensor", depth=False, resolution=None):
        resolution = tuple(resolution or (self.sensor_resolution if name == "sensor" else (512, 512)))
        if resolution not in self._renderers:
            self._renderers[resolution] = mujoco.Renderer(self.model, width=resolution[0], height=resolution[1])
        renderer = self._renderers[resolution]
        if depth:
            renderer.enable_depth_rendering()
        else:
            renderer.disable_depth_rendering()
        opt = mujoco.MjvOption()
        opt.geomgroup[3] = 0  # Panda 的碰撞代理隐藏，实际物理碰撞仍启用。
        renderer.update_scene(self.data, camera=name, scene_option=opt)
        return renderer.render().copy()

    def show(self, seconds=30):
        import mujoco.viewer
        with mujoco.viewer.launch_passive(self.model, self.data) as viewer:
            end = time.monotonic() + seconds
            while viewer.is_running() and time.monotonic() < end:
                viewer.sync()
                time.sleep(1/30)

    def close(self):
        for renderer in self._renderers.values():
            renderer.close()
        self._renderers.clear()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class SO100Env(RobotEnv):
    """保留 SO100 本地 URDF 的可读入口；新课默认使用 Panda。"""
    def __init__(self, **kwargs):
        super().__init__(robot="so100", **kwargs)

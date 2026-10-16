"""第六周课件实验：先运行 scene，再逐项比较，最后运行 suite 检查所有实践。"""
import argparse
import copy
import hashlib
import importlib.metadata
import json
from pathlib import Path
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]

import gymnasium as gym
import imageio.v2 as imageio
import numpy as np
import sapien
import torch
from mani_skill.utils import sapien_utils
from .scene import SO100Env
from .panda import PandaBasicEnv
from .robot import SO100Robot

OUTPUT = ROOT / "outputs/week06"
CASES = {
    "baseline": {},
    "camera": {"camera_eye": [0, -0.8, 0.4]},  # 单变量对照：仅移动 eye，target 保持默认值
    "side_camera": {"camera_eye": [0, -0.8, 0.4], "camera_target": [0, 0, 0]},
    "texture": {"ground_texture": "checkerboard"},
    "lighting": {"lighting_preset": "dark"},
    "fov60": {"camera_fov": np.pi / 3},
    "resolution256": {"sensor_resolution": [256, 256]},
    "qpos": {"initial_qpos_preset": "raised"},
    "human_camera": {"human_render_camera_configs": {"pose": [0, -0.8, 0.4]}},
    "viewer_camera": {"viewer_camera_configs": {"width": 800, "height": 600, "fov": np.pi / 3}},
    "panda": {"env_id": "RUC-Panda-v1"},
    # 练习的四个阶段固定使用 256×256，避免把分辨率变化误认成其他参数的作用。
    "exercise_baseline": {"sensor_resolution": [256, 256]},
    "exercise_texture": {"sensor_resolution": [256, 256], "ground_texture": "checkerboard"},
    "exercise_camera": {"sensor_resolution": [256, 256], "ground_texture": "checkerboard", "camera_preset": "oblique"},
    "exercise_final": {"sensor_resolution": [256, 256], "ground_texture": "checkerboard", "camera_preset": "oblique", "initial_qpos_preset": "raised"},
}


def arr(x):
    return x.detach().cpu().numpy() if isinstance(x, torch.Tensor) else np.asarray(x)


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def create_env(changes=None):
    changes = copy.deepcopy(changes or {})
    env_id = changes.pop("env_id", "RUC-SO100-v1")
    # 本课统一 CPU 物理、单环境和绝对关节目标，便于 macOS/Linux 对照。
    # rgbd 返回算法相机图像；render_rgb_array 则使用独立的演示相机。
    config = dict(num_envs=1, sim_backend="cpu", obs_mode="rgbd", reward_mode="none",
                  control_mode="pd_joint_pos", render_mode="rgb_array",
                  human_render_camera_configs=dict(width=512, height=512))
    for key in ("human_render_camera_configs", "viewer_camera_configs"):
        if key in changes:
            config.setdefault(key, {}).update(changes.pop(key))
    config.update(changes)
    # 将易读的 eye 坐标转换为 SAPIEN 的相机位姿。
    if "pose" in config["human_render_camera_configs"]:
        eye = config["human_render_camera_configs"]["pose"]
        config["human_render_camera_configs"]["pose"] = sapien_utils.look_at(eye, [0, 0, 0.15])
    return gym.make(env_id, **config)


def snapshot(env, obs, output):
    output.mkdir(parents=True, exist_ok=True)
    base = env.unwrapped
    # 观测保留批次维度，[0] 取唯一的环境。深度单位为毫米。
    rgb = arr(obs["sensor_data"]["base_camera"]["rgb"])[0]
    depth = arr(obs["sensor_data"]["base_camera"]["depth"])[0]
    human = arr(base.render_rgb_array())
    if human.ndim == 4:
        human = human[0]
    imageio.imwrite(output / "sensor_rgb.png", rgb)
    imageio.imwrite(output / "human_render.png", human)
    np.savez_compressed(output / "observations.npz", rgb=rgb, depth_mm=depth)
    links = {link.name: arr(link.pose.p).reshape(-1).tolist() for link in base.agent.robot.links}
    shapes = base.ground._objs[0].find_component_by_type(sapien.physx.PhysxRigidStaticComponent).collision_shapes
    materials = [dict(static_friction=s.physical_material.static_friction,
                      dynamic_friction=s.physical_material.dynamic_friction,
                      restitution=s.physical_material.restitution) for s in shapes]
    data = dict(qpos=arr(base.agent.robot.get_qpos())[0].tolist(),
                joint_names=[j.name for j in base.agent.robot.active_joints],
                action_shape=list(env.action_space.shape), control_mode=base.control_mode,
                qpos_size=int(base.agent.robot.get_qpos().shape[-1]),
                robot_urdf=str(base.agent.urdf_path), link_positions=links,
                camera_eye=base._camera_eye, camera_target=base._camera_target,
                camera_fov_rad=base._camera_fov, ambient_light=base._ambient_light,
                ground_texture=base._ground_texture, ground_materials=materials,
                sensor_rgb_shape=list(rgb.shape), sensor_depth_shape=list(depth.shape),
                sensor_intrinsic=arr(obs["sensor_param"]["base_camera"]["intrinsic_cv"])[0].tolist(),
                rgb_mean=float(rgb.mean()), human_render_shape=list(human.shape),
                simulation_hz=base.sim_freq, control_hz=base.control_freq)
    save_json(output / "result.json", data)
    return data


def scene(case, output, human_seconds=0, changes=None):
    requested = copy.deepcopy(CASES[case] if changes is None else changes)
    env = create_env(requested)
    try:
        obs, _ = env.reset(seed=0)
        result = snapshot(env, obs, output)
        result["case"] = case
        result["requested_changes"] = requested
        save_json(output / "result.json", result)
        if human_seconds:
            viewer = env.unwrapped.render_human()
            end = time.monotonic() + human_seconds
            # 这里只渲染，不执行 step，便于静态观察装配与相机。
            while time.monotonic() < end and not viewer.closed:
                env.unwrapped.render_human()
                time.sleep(1 / 30)
        print(f"Scene {case}: qpos={result['qpos_size']}, action={result['action_shape']}, image={result['sensor_rgb_shape']}", flush=True)
        return result
    finally:
        env.close()


def difference(a, b, filename="sensor_rgb.png"):
    x = imageio.imread(a / filename).astype(float)
    y = imageio.imread(b / filename).astype(float)
    return float(np.mean(np.abs(x - y)))


def compare(output):
    names = ["baseline", "camera", "side_camera", "texture", "lighting", "fov60", "resolution256",
             "qpos", "human_camera", "viewer_camera", "panda",
             "exercise_baseline", "exercise_texture", "exercise_camera", "exercise_final"]
    results = {name: scene(name, output / name) for name in names}
    base = results["baseline"]
    checks = {}
    for name in ("camera", "texture", "lighting", "fov60", "resolution256", "human_camera", "viewer_camera"):
        if results[name]["qpos"] != base["qpos"] or results[name]["link_positions"] != base["link_positions"]:
            raise AssertionError(f"{name} changed world robot state")
    for name in ("camera", "texture", "lighting", "fov60", "qpos"):
        delta = difference(output / "baseline", output / name)
        if delta < 0.05:
            raise AssertionError(f"{name} did not visibly affect sensor RGB")
        checks[name + "_rgb_mean_absolute_difference"] = delta
    # 图像变了不等于机器人动了：分别检查世界状态、摩擦和相机内参。
    assert results["texture"]["ground_materials"] == base["ground_materials"]
    assert results["lighting"]["rgb_mean"] < base["rgb_mean"]
    assert results["resolution256"]["sensor_rgb_shape"] == [256, 256, 3]
    k0 = np.array(base["sensor_intrinsic"])
    k60 = np.array(results["fov60"]["sensor_intrinsic"])
    k256 = np.array(results["resolution256"]["sensor_intrinsic"])
    assert np.isclose(k60[0, 0] / k0[0, 0], np.sqrt(3), rtol=1e-5)
    assert np.isclose(k256[0, 0] / k0[0, 0], 2, rtol=1e-5)
    for name in ("human_camera", "viewer_camera"):
        assert difference(output / "baseline", output / name) == 0, "Non-sensor camera changed sensor input"
    assert difference(output / "baseline", output / "human_camera", "human_render.png") > 1
    assert difference(output / "baseline", output / "camera", "human_render.png") == 0
    assert results["panda"]["qpos_size"] == 9 and results["panda"]["action_shape"] == [8]
    summary = dict(status="passed", slides=[43, 45, 46, 47, 48, 49, 50, 51, 52, 54, 58], checks=checks,
                   texture_preserves_friction=True, visual_settings_preserve_robot_state=True,
                   human_and_viewer_settings_preserve_sensor_image=True,
                   fov_focal_length_ratio=float(k60[0, 0] / k0[0, 0]), resolution_pixel_ratio=4,
                   baseline_mean_brightness=base["rgb_mean"], dark_mean_brightness=results["lighting"]["rgb_mean"],
                   panda_qpos_size=9, panda_action_size=8, cases=names)
    save_json(output / "comparison.json", summary)
    return summary


def reset_step(output):
    env = create_env()
    try:
        obs, _ = env.reset(seed=0)
        initial = snapshot(env, obs, output / "01_reset")
        q0 = np.array(initial["qpos"], dtype=np.float32)
        target = q0.copy()
        # pd_joint_pos 接收绝对目标角，连续 step 让 PD 控制器逐步靠近目标。
        target[0] += 0.3
        for _ in range(40):
            obs, *_ = env.step(target)
        moved = snapshot(env, obs, output / "02_step")
        obs, _ = env.reset(seed=0)
        restored = snapshot(env, obs, output / "03_reset_again")
        assert np.allclose(restored["qpos"], q0)
        assert abs(moved["qpos"][0] - q0[0]) > 0.25
        obs, _ = env.reset(seed=0, options={"initial_qpos": SO100Env.QPOS_PRESETS["raised"]})
        changed = snapshot(env, obs, output / "04_reset_new_qpos")
        assert np.allclose(changed["qpos"], SO100Env.QPOS_PRESETS["raised"])
        data = dict(status="passed", slides=[8, 11, 41, 42, 49], initial=initial["qpos"],
                    after_step=moved["qpos"], after_reset=restored["qpos"], new_initial=changed["qpos"],
                    steps=40, simulation_hz=env.unwrapped.sim_freq, control_hz=env.unwrapped.control_freq,
                    physical_substeps_per_action=env.unwrapped.sim_freq // env.unwrapped.control_freq)
        save_json(output / "result.json", data)
        return data
    finally:
        env.close()


def urdf_experiment(output):
    source = Path(SO100Robot.urdf_path)
    original_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    before = ET.parse(source)
    inventory = {
        "urdf": str(source),
        "links": [{"name": link.get("name"),
                   "visual_count": len(link.findall("visual")),
                   "collision_count": len(link.findall("collision")),
                   "mass_kg": float(link.find("inertial/mass").get("value")) if link.find("inertial/mass") is not None else None,
                   "inertia": link.find("inertial/inertia").attrib if link.find("inertial/inertia") is not None else None}
                  for link in before.getroot().findall("link")],
        "joints": [{"name": j.get("name"), "type": j.get("type"),
                    **{tag: j.find(tag).attrib if j.find(tag) is not None else None
                       for tag in ("parent", "child", "origin", "axis", "limit")}}
                   for j in before.getroot().findall("joint")],
    }
    save_json(output / "model_inventory.json", inventory)
    joint = before.getroot().find("joint[@name='shoulder_pan']")
    xyz = [float(v) for v in joint.find("origin").get("xyz").split()]
    old_xyz = xyz.copy()
    output.mkdir(parents=True, exist_ok=True)
    # 副本位于输出目录；使用绝对网格路径才能继续引用原模型资源。
    # 仅修改实验副本，不改写仓库内的 URDF。
    for mesh in before.getroot().findall(".//mesh"):
        mesh.set("filename", str((source.parent / mesh.get("filename")).resolve()))
    before.write(output / "before.urdf", encoding="utf-8", xml_declaration=True)
    xyz[2] += 0.05
    joint.find("origin").set("xyz", " ".join(str(x) for x in xyz))
    before.write(output / "after.urdf", encoding="utf-8", xml_declaration=True)
    initial_path = SO100Robot.urdf_path
    try:
        runs = {}
        for name in ("before", "after"):
            SO100Robot.urdf_path = str((output / f"{name}.urdf").resolve())
            runs[name] = scene("baseline", output / name, changes={"robot_uids": "so100_custom"})
    finally:
        SO100Robot.urdf_path = initial_path
    deltas = {name: (np.array(runs["after"]["link_positions"][name]) - np.array(pos)).tolist()
              for name, pos in runs["before"]["link_positions"].items()}
    assert np.allclose(deltas["Base"], 0, atol=1e-6)
    for name, delta in deltas.items():
        if name != "Base":
            assert np.allclose(delta, [0, 0, 0.05], atol=1e-6), (name, delta)
    assert original_hash == hashlib.sha256(source.read_bytes()).hexdigest()
    data = dict(status="passed", slides=list(range(27, 38)),
                joint="shoulder_pan", original_xyz=old_xyz, changed_xyz=xyz,
                world_link_displacements=deltas, original_file_preserved=True,
                note="SO100 shoulder_pan: z = 0.0165 m + 0.05 m = 0.0665 m; see slide 36.")
    save_json(output / "result.json", data)
    return data


def cube_drop(output):
    trials = {}
    for collision in (True, False):
        name = "collision_on" if collision else "collision_off"
        env = create_env(dict(add_cube=True, cube_collision=collision))
        try:
            obs, _ = env.reset(seed=0)
            base = env.unwrapped
            snapshot(env, obs, output / name / "initial")
            action = base.get_joint_positions().reshape(-1).astype(np.float32)
            heights = [float(arr(base.cube.pose.p)[0, 2])]
            frames = []
            # 开启碰撞运行 4 s，等待稳定；无碰撞只需 0.6 s 即可观察穿地。
            count = 80 if collision else 12
            for i in range(count):
                obs, *_ = env.step(action)
                heights.append(float(arr(base.cube.pose.p)[0, 2]))
                if i % 2 == 0:
                    frames.append(arr(base.render_rgb_array())[0])
            snapshot(env, obs, output / name / "final")
            assert np.isfinite(heights).all()
            # 检查物理结果，而不只检查脚本能否退出：方块中心应停在半边长处。
            if collision:
                assert abs(heights[-1] - 0.02) < 0.002, heights[-1]
                assert max(heights[-10:]) - min(heights[-10:]) < 0.001
            else:
                assert heights[-1] < -0.05, heights[-1]
            np.savez_compressed(output / name / "height_trace.npz",
                                time_s=np.arange(len(heights)) / base.control_freq, center_z_m=heights)
            imageio.mimsave(output / name / "drop.gif", frames, duration=100, loop=0)
            obs, _ = env.reset(seed=0)
            reset_z = float(arr(base.cube.pose.p)[0, 2])
            assert abs(reset_z - 0.3) < 1e-6
            trials[name] = dict(initial_center_z_m=heights[0], final_center_z_m=heights[-1],
                                reset_center_z_m=reset_z, steps=count,
                                simulation_seconds=count / base.control_freq)
        finally:
            env.close()
    data = dict(status="passed", slides=[5, 6, 10, 12, 29, 37, 55, 56], cube_side_m=0.04,
                gravity=[0, 0, -9.81], ground_z_m=0, expected_center_z_m=0.02,
                tolerance_m=0.002, trials=trials)
    save_json(output / "result.json", data)
    return data


def official_demo(output):
    # 只验证官方任务可创建、运行和渲染；随机动作不代表抓取策略。
    env = gym.make("PickCube-v1", num_envs=1, sim_backend="cpu", obs_mode="state",
                   control_mode="pd_joint_delta_pos", render_mode="rgb_array",
                   human_render_camera_configs=dict(width=512, height=512))
    try:
        output.mkdir(parents=True, exist_ok=True)
        env.reset(seed=0)
        env.action_space.seed(0)
        for _ in range(30):
            obs, reward, terminated, truncated, info = env.step(env.action_space.sample())
            assert np.isfinite(arr(obs)).all()
        imageio.imwrite(output / "pickcube.png", arr(env.render())[0])
        data = dict(status="passed", slide=21, env_id="PickCube-v1", steps=30,
                    control_mode=env.unwrapped.control_mode, action_shape=list(env.action_space.shape),
                    scope="Official task creation, random steps and rendering; not grasp success")
        save_json(output / "result.json", data)
        return data
    finally:
        env.close()


def time_example(output):
    positions = np.arange(101) * 0.2 * 0.01
    data = dict(slide=9, status="passed", velocity_m_s=0.2, dt_s=0.01, displacement_per_step_m=0.002,
                steps=100, elapsed_simulated_s=1, displacement_m=float(positions[-1]),
                scope="Arithmetic illustration assuming constant velocity, no gravity or collisions")
    assert np.isclose(positions[-1], 0.2)
    save_json(output / "result.json", data)
    return data


def suite(output):
    checks = {}
    for name, function in (("time", time_example), ("official", official_demo), ("urdf", urdf_experiment),
                           ("reset_step", reset_step), ("compare", compare), ("cube_drop", cube_drop)):
        print(f"Running lesson experiment: {name}", flush=True)
        try:
            checks[name] = function(output / name)
        except Exception as exc:
            save_json(output / "suite.json", dict(status="failed", checks=checks, failed=name,
                                                   error=f"{type(exc).__name__}: {exc}"))
            raise
    summary = dict(status="passed", source_deck="第六周_仿真平台_RoboticsIntro_课程仓库版.pptx", slide_count=59,
                   versions={n: importlib.metadata.version(n) for n in ("mani-skill", "sapien", "torch")}, checks=checks)
    save_json(output / "suite.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", nargs="?", default="scene",
                        choices=["scene", "compare", "urdf", "reset-step", "cube-drop", "official", "time", "suite"])
    parser.add_argument("--case", choices=list(CASES), default="baseline")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--human", action="store_true", help="Open a static scene for classroom inspection")
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--texture", type=Path, help="自定义地面 PNG/JPG，仅用于 scene")
    args = parser.parse_args(argv)
    if args.human and args.experiment != "scene":
        parser.error("--human is for scene; other experiments save images automatically")
    if args.texture and args.experiment != "scene":
        parser.error("--texture 仅用于 scene；suite 使用固定的对照条件")
    if args.seconds < 0:
        parser.error("--seconds 不能为负数")
    if args.experiment == "scene":
        changes = copy.deepcopy(CASES[args.case])
        if args.texture:
            changes["ground_texture"] = str(args.texture.resolve())
        scene(args.case, args.output / "scene" / args.case, args.seconds if args.human else 0, changes)
    else:
        functions = {"compare": compare, "urdf": urdf_experiment, "reset-step": reset_step,
                     "cube-drop": cube_drop, "official": official_demo, "time": time_example, "suite": suite}
        target = args.output if args.experiment == "suite" else args.output / args.experiment.replace("-", "_")
        functions[args.experiment](target)


if __name__ == "__main__":
    main()

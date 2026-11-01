"""第六周可复现实验与断言；每次只改一个物理或成像因素。"""
import argparse
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import mujoco
import numpy as np
from PIL import Image

from .robot import ROOT, SO100_DIR
from .scene import RobotEnv

OUTPUT = ROOT / "outputs/week06"
CASES = {
    "baseline": {},
    "camera": {"camera_eye": [0, -1.2, .7]},
    "side_camera": {"camera_eye": [0, -1.2, .7], "camera_target": [.2, 0, .2]},
    "texture": {"ground_texture": "checkerboard"},
    "lighting": {"lighting_preset": "dark"},
    "fov60": {"camera_fov": np.pi/3},
    "resolution256": {"sensor_resolution": [256, 256]},
    "qpos": {"initial_qpos_preset": "raised"},
    "human_camera": {"human_eye": [0, -1.2, .6]},
    "so100": {"robot": "so100"},
    "exercise_baseline": {"sensor_resolution": [256, 256]},
    "exercise_texture": {"sensor_resolution": [256, 256], "ground_texture": "checkerboard"},
    "exercise_camera": {"sensor_resolution": [256, 256], "ground_texture": "checkerboard", "camera_eye": [.8, -.8, .7], "camera_target": [.3, 0, .3]},
    "exercise_final": {"sensor_resolution": [256, 256], "ground_texture": "checkerboard", "camera_eye": [.8, -.8, .7], "camera_target": [.3, 0, .3], "initial_qpos_preset": "raised"},
}


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")


def create_env(changes=None):
    return RobotEnv(**(changes or {}))


def snapshot(env, output, render=True):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    params = env.camera_params()
    result = dict(robot=env.robot, qpos=env.qpos.tolist(), qpos_size=len(env.qpos),
                  joint_names=env.joint_names, action_shape=[env.model.nu],
                  control_mode="absolute_joint_position_pd", simulation_hz=env.sim_hz,
                  control_hz=env.control_hz, depth_unit="m", time=float(env.data.time),
                  camera_eye=env.camera_eye, camera_target=env.camera_target,
                  camera_fov_rad=env.camera_fov, sensor_intrinsic=params["K"].tolist(),
                  T_world_camera_cv=params["T_world_camera_cv"].tolist(),
                  ground_friction=env.model.geom("floor").friction.tolist(),
                  ground_texture=env.ground_texture,
                  link_positions={env.model.body(i).name: env.data.xpos[i].tolist() for i in range(1, env.model.nbody)},
                  rendered=render)
    (output / "scene.xml").write_text(env.xml, encoding="utf-8")
    if render:
        rgb, depth, human = env.render(), env.render(depth=True), env.render("demo")
        Image.fromarray(rgb).save(output / "sensor_rgb.png")
        Image.fromarray(human).save(output / "human_render.png")
        np.savez_compressed(output / "observations.npz", rgb=rgb, depth_m=depth)
        result.update(sensor_rgb_shape=list(rgb.shape), sensor_depth_shape=list(depth.shape), rgb_mean=float(rgb.mean()))
    save_json(output / "result.json", result)
    return result


def scene(case, output, human_seconds=0, changes=None, render=True):
    requested = dict(CASES[case] if changes is None else changes)
    with create_env(requested) as env:
        result = snapshot(env, output, render)
        result.update(case=case, requested_changes=requested)
        save_json(Path(output) / "result.json", result)
        if human_seconds:
            env.show(human_seconds)
        print(f"scene {case}: {env.robot}, qpos={len(env.qpos)}, action={env.model.nu}, rendered={render}", flush=True)
        return result


def difference(a, b, name="sensor_rgb.png"):
    x, y = np.array(Image.open(Path(a)/name), float), np.array(Image.open(Path(b)/name), float)
    return float(np.mean(np.abs(x-y)))


def compare(output, render=True):
    results = {name: scene(name, output/name, render=render) for name in CASES}
    base = results["baseline"]
    checks = {}
    for name in ("camera", "side_camera", "texture", "lighting", "fov60", "resolution256", "human_camera"):
        assert results[name]["qpos"] == base["qpos"], name
        assert results[name]["link_positions"] == base["link_positions"], name
    assert results["texture"]["ground_friction"] == base["ground_friction"]
    assert np.isclose(results["fov60"]["sensor_intrinsic"][0][0]/base["sensor_intrinsic"][0][0], np.sqrt(3))
    assert np.isclose(results["resolution256"]["sensor_intrinsic"][0][0]/base["sensor_intrinsic"][0][0], 2)
    if render:
        for name in ("camera", "texture", "lighting", "fov60", "qpos"):
            delta = difference(output/"baseline", output/name)
            assert delta > .05, (name, delta)
            checks[name+"_image_difference"] = delta
        assert results["lighting"]["rgb_mean"] < base["rgb_mean"]
        assert difference(output/"baseline", output/"human_camera") == 0
        assert difference(output/"baseline", output/"human_camera", "human_render.png") > .05
        assert results["resolution256"]["sensor_rgb_shape"] == [256, 256, 3]
    result = {"status": "passed", "scenes": len(results), "image_checks_run": render, "checks": checks}
    save_json(output/"result.json", result)
    return result


def reset_step(output, render=True):
    with RobotEnv() as env:
        initial = env.qpos.copy()
        snapshot(env, output/"01_reset", render)
        action = env.data.ctrl.copy()
        action[0] = .3
        for _ in range(100):
            env.step(action)
        moved = env.qpos.copy()
        snapshot(env, output/"02_step", render)
        assert abs(moved[0]-.3) < .01, moved[0]
        assert abs(env.data.time-2) < 1e-8
        env.reset()
        snapshot(env, output/"03_reset_again", render)
        assert np.array_equal(env.qpos, initial)
        assert np.all(env.data.qvel == 0) and env.data.time == 0
        result = dict(status="passed", before=initial.tolist(), after=moved.tolist(), reset=env.qpos.tolist(), simulated_seconds=2)
        save_json(output/"result.json", result)
        return result


def urdf_experiment(output, render=True):
    output.mkdir(parents=True, exist_ok=True)
    source = SO100_DIR/"so100.urdf"
    before_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    root = ET.parse(source)
    origin = root.find(".//joint[@name='shoulder_pan']/origin")
    xyz = np.fromstring(origin.get("xyz"), sep=" ")
    xyz[2] += .05
    origin.set("xyz", " ".join(map(str, xyz)))
    (output/"before.urdf").write_bytes(source.read_bytes())
    root.write(output/"after.urdf", encoding="utf-8", xml_declaration=True)
    results = {}
    for name in ("before", "after"):
        with RobotEnv(robot="so100", urdf_path=output/(name+".urdf")) as env:
            results[name] = snapshot(env, output/name, render)
    a, b = [results[x]["link_positions"] for x in ("before", "after")]
    assert np.allclose(a["Base"], b["Base"], atol=1e-8)
    shifts = {name: (np.array(b[name])-pos).tolist() for name, pos in a.items() if name != "Base"}
    assert all(np.allclose(x, [0, 0, .05], atol=1e-6) for x in shifts.values())
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before_hash
    result = dict(status="passed", source_unchanged=True, source_sha256=before_hash, downstream_shifts_m=shifts)
    save_json(output/"result.json", result)
    return result


def cube_drop(output, render=True):
    result = {"status": "passed", "cases": {}}
    for name, collision, gravity in (("collision", True, (0, 0, -9.81)), ("no_collision", False, (0, 0, -9.81)), ("zero_gravity", True, (0, 0, 0))):
        frames, trace = [], []
        with RobotEnv(add_cube=True, cube_collision=collision, cube_position=(.65, .3, .3), gravity=gravity) as env:
            initial = env.cube_xyz.copy()
            action = env.data.ctrl.copy()
            for i in range(100):
                env.step(action)
                trace.append([float(env.data.time), *env.cube_xyz.tolist()])
                if render and i % 5 == 0:
                    frames.append(Image.fromarray(env.render("demo")))
            final = float(env.cube_xyz[2])
            if name == "collision":
                assert abs(final-.02) < .002, final
            elif name == "no_collision":
                assert final < -1., final
            else:
                assert np.allclose(env.cube_xyz, initial), env.cube_xyz
            snapshot(env, output/name, render)
            np.savez_compressed(output/name/"height_trace.npz", time_xyz=np.array(trace))
            if frames:
                frames[0].save(output/name/"drop.gif", save_all=True, append_images=frames[1:], duration=100, loop=0)
            env.reset()
            assert np.allclose(env.cube_xyz, initial) and np.all(env.data.qvel == 0)
            result["cases"][name] = {"final_z_m": final, "reset_restored": True}
    save_json(output/"result.json", result)
    return result


def time_experiment(output):
    dt = 1/500
    velocity = .2
    position = 0.
    for _ in range(500):
        position += velocity*dt
    assert abs(position-.2) < 1e-12
    result = dict(status="passed", dt_s=dt, steps=500, duration_s=1, velocity_m_s=velocity, final_position_m=position)
    save_json(output/"result.json", result)
    return result


def suite(output, render=True):
    functions = {"time": lambda: time_experiment(output/"time"),
                 "reset_step": lambda: reset_step(output/"reset_step", render),
                 "urdf": lambda: urdf_experiment(output/"urdf", render),
                 "cube_drop": lambda: cube_drop(output/"cube_drop", render),
                 "compare": lambda: compare(output/"compare", render)}
    results = {}
    for name, function in functions.items():
        try:
            results[name] = function()
        except Exception as error:
            save_json(output/"suite.json", {"status": "failed", "failed_experiment": name, "error": str(error), "completed": list(results)})
            raise
    result = {"status": "passed", "mujoco": mujoco.__version__, "rendered": render, "experiments": results}
    save_json(output/"suite.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", default="scene", choices=["scene", "compare", "reset-step", "urdf", "cube-drop", "time", "suite"])
    parser.add_argument("--case", default="baseline", choices=list(CASES))
    parser.add_argument("--robot", choices=["panda", "so100"])
    parser.add_argument("--texture", type=Path)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--human", action="store_true", help="scene 交互查看；macOS 使用 mjpython")
    parser.add_argument("--seconds", type=float, default=30)
    parser.add_argument("--no-render", action="store_true", help="只验证物理/数值；不会假称渲染验证通过")
    args = parser.parse_args(argv)
    if args.command != "scene" and (args.human or args.texture or args.robot):
        parser.error("--human/--texture/--robot apply only to scene")
    if args.command == "scene":
        changes = dict(CASES[args.case])
        if args.robot:
            changes["robot"] = args.robot
        if args.texture:
            changes["ground_texture"] = str(args.texture.resolve())
        return scene(args.case, args.output/"scene"/args.case, args.seconds if args.human else 0, changes, not args.no_render)
    if args.command == "suite":
        result = suite(args.output, not args.no_render)
    elif args.command == "time":
        result = time_experiment(args.output/"time")
    else:
        fn = {"compare": compare, "reset-step": reset_step, "urdf": urdf_experiment, "cube-drop": cube_drop}[args.command]
        result = fn(args.output/args.command.replace("-", "_"), not args.no_render)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result


if __name__ == "__main__":
    main()

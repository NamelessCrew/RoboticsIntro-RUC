"""原生 MuJoCo Panda 方块抓取：known→规划→控制；vision 只替换目标位置来源。"""
import argparse
import math
from pathlib import Path

import mujoco
import numpy as np
from PIL import Image, ImageDraw

from chapters.week06.experiments import save_json, snapshot
from chapters.week06.robot import ROOT
from chapters.week06.scene import RobotEnv
from .planner import LinearPlanner, PlannerConfig
from .controller import CartesianController, bilateral_contacts
from .perception import locate_red_cube
from .live_viewer import LiveViewer, ViewerClosed
from .video import TaskVideo


def make_env(cube_xy=(.45, 0), cube_friction=1.):
    return RobotEnv(add_cube=True, cube_position=(*cube_xy, .0201), cube_friction=cube_friction,
                    sensor_resolution=(320, 240), camera_eye=(.45, 0, .85),
                    camera_target=(.45, 0, 0), camera_fov=np.pi/4)


def summarize_hold(records, initial_z):
    if not records:
        return {"stable_hold": False, "hold_samples": 0, "bilateral_contact_fraction": 0., "lifted_fraction": 0.}
    positions = np.array([r["cube_xyz_m"] for r in records])
    tcp = np.array([r["tcp_xyz_m"] for r in records])
    relative = positions-tcp
    deviation = float(np.max(np.linalg.norm(relative-relative.mean(axis=0), axis=1)))
    contact_fraction = float(np.mean([r["bilateral"] for r in records]))
    lifted_fraction = float(np.mean(positions[:, 2]-initial_z >= .06))
    max_speed = float(max(r["cube_speed_m_s"] for r in records))
    stable = len(records) >= 50 and contact_fraction >= .9 and lifted_fraction >= .9 and max_speed < .02 and deviation < .005
    return {"stable_hold": bool(stable), "hold_samples": len(records),
            "bilateral_contact_fraction": contact_fraction, "lifted_fraction": lifted_fraction,
            "minimum_hold_lift_m": float(np.min(positions[:, 2]-initial_z)),
            "maximum_hold_speed_m_s": max_speed, "max_tcp_relative_deviation_m": deviation}


def evaluate(env, initial_z, hold_records=None):
    grasped, forces = bilateral_contacts(env)
    lifted = float(env.cube_xyz[2]-initial_z)
    hold = summarize_hold(hold_records, initial_z)
    return {"is_grasped": bool(grasped), "is_lifted": lifted >= .06,
            "lift_distance_m": lifted, **hold,
            "finger_normal_forces_N": forces, "cube_xyz_m": env.cube_xyz.tolist(),
            "success": bool(grasped and lifted >= .06 and hold["stable_hold"])}


def save_trajectory(output, rows):
    save_json(output/"trajectory.json", rows)
    np.savez_compressed(output/"trajectory.npz", time_s=np.array([r["time_s"] for r in rows]),
                        tcp_xyz_m=np.array([r["tcp_xyz_m"] for r in rows]),
                        cube_xyz_m=np.array([r["cube_xyz_m"] for r in rows]),
                        qpos=np.array([r["qpos"] for r in rows]))


def run_task(mode="known", output=None, render=True, cube_xy=(.45, 0), release_check=False,
             close_gripper=True, human=False, speed=1., save_images=False, video=True):
    if mode not in ("known", "vision"):
        raise ValueError("mode must be known or vision")
    if not render and (mode == "vision" or save_images):
        raise ValueError("vision/--save-images require rendering; remove --no-render")
    output = Path(output or ROOT/"outputs/week07"/mode)
    rows = []
    recorder = TaskVideo(output, enabled=render and video)
    try:
        with recorder:
            result = _run_task(mode, output, render, cube_xy, release_check, close_gripper,
                               human, speed, save_images, recorder, rows)
    except ViewerClosed:
        result = {"status": "aborted", "success": False, "reason": "viewer_closed", "mode": mode,
                  "rendered": render, "human": human, "speed": speed}
        message = "；部分视频保留为 grasp.partial.mp4" if recorder.frames else ""
        print("窗口已关闭，任务已中止"+message+"。", flush=True)
    except BaseException as error:
        save_trajectory(output, rows)
        save_json(output/"result.json", {"status": "failed", "success": False, "error": str(error), "video": recorder.metadata()})
        raise
    save_trajectory(output, rows)
    result["video"] = recorder.metadata()
    save_json(output/"result.json", result)
    return result


def _run_task(mode, output, render, cube_xy, release_check, close_gripper, human, speed, save_images, recorder, rows):
    output.mkdir(parents=True, exist_ok=True)
    hold_records = []
    phase = {"stage": "initial_settle", "target": None}
    with make_env(cube_xy) as env, LiveViewer(env, enabled=human, speed=speed) as live:
        def after_step():
            bilateral, forces = bilateral_contacts(env)
            cube_dadr = env.model.joint("cube_free").dofadr[0]
            rows.append({"cube_speed_m_s": float(np.linalg.norm(env.data.qvel[cube_dadr:cube_dadr+3])),
                         "time_s": float(env.data.time), "stage": phase["stage"],
                         "target_xyz_m": list(phase["target"]) if phase["target"] is not None else None,
                         "tcp_xyz_m": env.tcp_xyz.tolist(), "cube_xyz_m": env.cube_xyz.tolist(),
                         "qpos": env.qpos.tolist(), "ctrl": env.data.ctrl.tolist(),
                         "bilateral": bilateral, "finger_forces_N": forces})
            recorder.capture(env)
            live.after_step()

        def stage_image(name):
            if save_images:
                snapshot(env, output/name, render=True)

        controller = CartesianController(env, on_step=after_step)
        planner = LinearPlanner(PlannerConfig(dt=1/env.control_hz, speed=.08))
        recorder.capture(env)  # 包含初始姿态；之后每0.1秒仿真时间采样，不受窗口倍速影响。
        for _ in range(25):
            controller.hold(True)
        initial = env.cube_xyz.copy()
        stage_image("01_initial")
        calibration = env.camera_params()
        save_json(output/"calibration.json", {key: value.tolist() if isinstance(value, np.ndarray) else value for key, value in calibration.items()})
        if mode == "vision":
            rgb, depth = env.render(), env.render(depth=True)
            position, detection = locate_red_cube(rgb, depth, calibration)
            if save_images:
                annotated = Image.fromarray(rgb)
                ImageDraw.Draw(annotated).rectangle(detection["bbox_xyxy"], outline="lime", width=2)
                annotated.save(output/"detection.png")
            detection["position_world_m"] = position.tolist()
            # 真值仅用于独立评估，不反馈给规划器/控制器。
            detection["ground_truth_m"] = initial.tolist()
            detection["localization_error_m"] = float(np.linalg.norm(position-initial))
            save_json(output/"localization.json", detection)
        else:
            position = initial.copy()
            detection = {"method": "simulator_ground_truth", "position_world_m": position.tolist()}

        def move(stage, target, opened):
            waypoints = planner.plan(env.tcp_xyz, target)
            for point in waypoints:
                phase.update(stage=stage, target=point)
                controller.move_to(point, opened)
            phase.update(stage=stage+"_settle", target=target)
            for _ in range(15):
                controller.hold(opened)
            error = float(np.linalg.norm(env.tcp_xyz-target))
            print(f"{mode} {stage}: {len(waypoints)} trajectory points; TCP error {1000*error:.2f} mm", flush=True)
            if error > .015:
                raise AssertionError(f"tracking error {error:.4f} m")

        approach = position + [0, 0, .16]
        grasp = position + [0, 0, .003]
        lift = grasp + [0, 0, .12]
        move("approach", approach, True)
        stage_image("02_approach")
        move("descend", grasp, True)
        stage_image("03_descend")
        phase.update(stage="close", target=grasp)
        for _ in range(75):
            controller.hold(not close_gripper)
        stage_image("04_closed")
        move("lift", lift, not close_gripper)
        phase.update(stage="hold", target=lift)
        for _ in range(50):
            controller.hold(not close_gripper)
            hold_records.append(rows[-1])
        stage_image("05_lifted")
        evaluation = evaluate(env, initial[2], hold_records)
        evaluation.update(status="completed", mode=mode, localization=detection,
                          rendered=bool(mode == "vision" or save_images or recorder.enabled),
                          human=human, speed=speed, save_images=save_images,
                          hold_duration_s=1., object_constraint="freejoint; contact and gravity only",
                          mujoco=mujoco.__version__, cube_initial_xyz_m=initial.tolist())
        if release_check:
            before_release = env.cube_xyz.copy()
            phase.update(stage="release", target=lift)
            for _ in range(100):
                controller.hold(True)
            after = evaluate(env, initial[2])
            evaluation["release_check"] = {"object_fell": bool(env.cube_xyz[2] < before_release[2]-.05), "after_release": after}
            stage_image("06_released")
            assert evaluation["release_check"]["object_fell"] and not after["success"], evaluation["release_check"]
        print(f"{mode}: success={evaluation['success']}, lift={evaluation['lift_distance_m']:.4f} m, bilateral={evaluation['bilateral_contact_fraction']:.2f}", flush=True)
        live.finish()
        return evaluation


def positive_speed(value):
    speed = float(value)
    if not math.isfinite(speed) or speed <= 0:
        raise argparse.ArgumentTypeError("speed must be positive and finite")
    return speed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["known", "vision"], default="known")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--no-render", action="store_true", help="已知位置任务不渲染/不保存媒体；不影响实时窗口")
    parser.add_argument("--no-video", action="store_true", help="不保存MP4；视觉任务仍获取RGB-D")
    parser.add_argument("--save-images", action="store_true", help="额外保存各阶段教学截图、RGB-D与检测图")
    parser.add_argument("--human", action="store_true", help="实时显示整个物理抓取；关闭窗口中止")
    parser.add_argument("--speed", type=positive_speed, default=1., help="窗口速度，默认1；不改变视频时间轴")
    parser.add_argument("--cube-x", type=float, default=.45)
    parser.add_argument("--cube-y", type=float, default=0.)
    parser.add_argument("--release-check", action="store_true", help="成功后打开夹爪，验证物体会自然落下")
    parser.add_argument("--keep-open", action="store_true", help="负对照：全程张开夹爪，预期抓取失败")
    args = parser.parse_args(argv)
    if args.no_render and (args.mode == "vision" or args.save_images):
        parser.error("vision/--save-images require rendering")
    result = run_task(args.mode, args.output, not args.no_render, (args.cube_x, args.cube_y),
                      args.release_check, not args.keep_open, args.human, args.speed, args.save_images, not args.no_video)
    if result.get("status") == "aborted":
        return result
    if result["success"] == args.keep_open:
        raise SystemExit("Unexpected grasp outcome; inspect result.json")
    return result


if __name__ == "__main__":
    main()

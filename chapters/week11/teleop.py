"""第十一周键盘遥操：沿世界坐标平移、旋转 Panda 末端并控制夹爪开合。"""

import argparse
import csv
from pathlib import Path
import time

import glfw
import mujoco
import numpy as np

from chapters.week07.controller import CartesianController, orientation_error
from chapters.week07.grasp import make_env


# 键名与 GLFW 常量对应；方向分量依次为世界坐标 X、Y、Z。
KEY_DIRECTIONS = {
    "W": (1, 0, 0), "S": (-1, 0, 0),
    "A": (0, 1, 0), "D": (0, -1, 0),
    "Q": (0, 0, 1), "E": (0, 0, -1),
}
KEY_ROTATIONS = {
    "Z": (1, 0, 0), "X": (-1, 0, 0),
    "T": (0, 1, 0), "G": (0, -1, 0),
    "C": (0, 0, 1), "V": (0, 0, -1),
}
ANGULAR_SPEED = np.deg2rad(30)  # rad/s
ACCELERATION = 0.30  # m/s²
MAX_SPEED = 0.08  # m/s
RELEASE_DECAY = 0.9  # 每个 50 Hz 控制周期
STOP_SPEED = 0.001  # m/s
MAX_RISE = 0.12  # m，相对起点的抬升上限
MIN_Z = 0.02  # m，限制末端目标高度；整臂碰撞仍由仿真处理


def read_direction(is_down, mapping=KEY_DIRECTIONS):
    """累加按住的方向键，并把组合向量的长度限制在 1 以内。"""
    direction = np.zeros(3)
    for key, axis in mapping.items():
        if is_down(key):
            direction += axis
    return direction / max(1.0, np.linalg.norm(direction))


class PandaTeleop:
    """把每轮输入转换为末端目标，并复用抓取作业的控制器。"""

    def __init__(self, env):
        self.env = env
        self.controller = CartesianController(env)
        self.dt = 1 / env.control_hz
        for _ in range(env.control_hz):
            self.controller.hold(gripper_open=True)
        self.target = env.tcp_xyz
        self.rotation = self.controller.rotation.copy()
        self.ceiling = self.target[2] + MAX_RISE
        self.velocity = np.zeros(3)
        self.gripper_open = True
        self.gripper_key_was_down = False

    def step(self, direction, gripper_key_down=False, *, angular_direction=None, clear=False):
        if clear:
            self.velocity.fill(0)
            self.gripper_open = True
            self.gripper_key_was_down = gripper_key_down
            self.controller.hold(gripper_open=True)
            return
        # K 只在刚按下的一轮切换，持续按住时保留同一个目标。
        was_down = self.gripper_key_was_down
        pressed_now = gripper_key_down and not was_down
        if pressed_now:
            self.gripper_open = not self.gripper_open
        self.gripper_key_was_down = gripper_key_down

        # 1. 从方向更新指令速度；松开后逐周期衰减。
        if direction.any():
            self.velocity += ACCELERATION * direction * self.dt
        else:
            self.velocity *= RELEASE_DECAY
        speed = np.linalg.norm(self.velocity)
        if speed > MAX_SPEED:
            self.velocity *= MAX_SPEED / speed
        elif speed < STOP_SPEED:
            self.velocity.fill(0)

        # 2. 把速度变为这一周期的位移，更新笛卡尔目标。
        candidate = self.target + self.velocity * self.dt
        bounded_z = np.clip(candidate[2], MIN_Z, self.ceiling)
        if bounded_z != candidate[2]:
            candidate[2] = bounded_z
            self.velocity[2] = 0

        # 世界轴旋转左乘；只转朝向，位置目标仍由平移通道更新。
        rotation = self.rotation
        if angular_direction is not None and angular_direction.any():
            magnitude = np.linalg.norm(angular_direction)
            axis = angular_direction / magnitude
            angle = ANGULAR_SPEED * magnitude * self.dt
            quat, matrix = np.empty(4), np.empty(9)
            mujoco.mju_axisAngle2Quat(quat, axis, angle)
            mujoco.mju_quat2Mat(matrix, quat)
            delta_rotation = matrix.reshape(3, 3)
            rotation = delta_rotation @ self.rotation

        # 3. 用作业已有的 IK 和关节 PD 执行；停下时继续保持目标。
        if np.array_equal(candidate, self.target) and rotation is self.rotation:
            self.controller.hold(gripper_open=self.gripper_open)
            return
        try:
            self.controller.move_to(
                candidate, gripper_open=self.gripper_open, rotation=rotation
            )
        except ValueError as error:
            self.velocity.fill(0)
            self.controller.hold(gripper_open=self.gripper_open)
            print(f"保持当前关节目标：{error}", flush=True)
        else:
            self.target = candidate
            self.rotation = rotation


def run_window(teleop, *, duration=None):
    """GLFW 提供持续的按键状态，MuJoCo 渲染同一个仿真场景。"""
    if not glfw.init():
        raise RuntimeError("无法初始化 GLFW，请在桌面会话中运行。")
    context = None
    try:
        window = glfw.create_window(960, 640, "Panda Keyboard Teleoperation", None, None)
        if not window:
            raise RuntimeError("无法创建 MuJoCo 遥操窗口。")
        glfw.make_context_current(window)
        glfw.swap_interval(1)

        model, data = teleop.env.model, teleop.env.data
        camera = mujoco.MjvCamera()
        camera.type = mujoco.mjtCamera.mjCAMERA_FIXED
        camera.fixedcamid = model.camera("demo").id
        option = mujoco.MjvOption()
        option.geomgroup[3] = 0
        scene = mujoco.MjvScene(model, maxgeom=2000)
        context = mujoco.MjrContext(model, mujoco.mjtFontScale.mjFONTSCALE_150)

        print("点击窗口后操作：W/S、A/D、Q/E 平移；Z/X、T/G、C/V 旋转；K 开合；R 清指令；Esc 退出。", flush=True)

        def is_down(key):
            if not glfw.get_window_attrib(window, glfw.FOCUSED):
                return False
            key_code = getattr(glfw, f"KEY_{key}")
            return glfw.get_key(window, key_code) == glfw.PRESS

        input_was_active = False
        clear_was_down = False
        require_release = False
        control_keys = (*KEY_DIRECTIONS, *KEY_ROTATIONS, "K")
        opened_at = time.monotonic()
        rendered_frames = 0
        while not glfw.window_should_close(window):
            start = time.monotonic()
            glfw.poll_events()
            if glfw.window_should_close(window) or glfw.get_key(window, glfw.KEY_ESCAPE) == glfw.PRESS:
                break
            clear_down = is_down("R")
            # R 清除指令后先等旧按键全部释放，避免松开 R 就恢复运动。
            if clear_down:
                require_release = True
            elif require_release:
                require_release = any(is_down(key) for key in control_keys)

            direction = read_direction(is_down) if not require_release else np.zeros(3)
            angular = read_direction(is_down, KEY_ROTATIONS) if not require_release else np.zeros(3)
            teleop.step(
                direction,
                gripper_key_down=not require_release and is_down("K"),
                angular_direction=angular,
                clear=clear_down and not clear_was_down,
            )
            clear_was_down = clear_down
            input_active = bool(direction.any() or angular.any())
            if input_active != input_was_active:
                print(
                    f"运动输入 {'启用' if input_active else '释放'} | TCP {teleop.env.tcp_xyz.round(4)}",
                    flush=True,
                )
                input_was_active = input_active

            width, height = glfw.get_framebuffer_size(window)
            if width and height:
                viewport = mujoco.MjrRect(0, 0, width, height)
                mujoco.mjv_updateScene(model, data, option, None, camera,
                                       mujoco.mjtCatBit.mjCAT_ALL, scene)
                mujoco.mjr_render(viewport, scene, context)
                x, y, z = teleop.env.tcp_xyz
                gripper = "OPEN" if teleop.gripper_open else "CLOSE"
                line = f"TCP (m): {x:.3f}, {y:.3f}, {z:.3f}   K command: {gripper}"

                mujoco.mjr_overlay(mujoco.mjtFontScale.mjFONTSCALE_150,
                                    mujoco.mjtGridPos.mjGRID_TOPLEFT, viewport,
                                    "Move W/S A/D Q/E | Rotate Z/X T/G C/V | K Grip | R Clear", line, context)
                glfw.swap_buffers(window)
                rendered_frames += 1
            if duration is not None and time.monotonic() - opened_at >= duration:
                break
            time.sleep(max(0, teleop.dt - (time.monotonic() - start)))
        if duration is not None:
            if not rendered_frames:
                raise RuntimeError("图形自检未渲染任何画面，请在本机桌面环境运行。")
            print(f"图形自检通过：已打开 GLFW 窗口并渲染 {rendered_frames} 帧，窗口已自动关闭。", flush=True)
    finally:
        if context is not None:
            context.free()
        glfw.terminate()


def check_full_controls(env, output):
    rows = []
    for keys in [(key,) for key in KEY_DIRECTIONS] + [("Q", "W"), ("Q", "E")]:
        env.reset()
        teleop = PandaTeleop(env)
        start = env.tcp_xyz
        direction = read_direction(lambda key: key in keys)
        for tick in range(150):
            teleop.step(direction if tick < 25 else np.zeros(3))
        delta = env.tcp_xyz - start
        active = direction != 0
        if (np.any(delta[active] * np.sign(direction[active]) < 0.02) or
                np.any(np.abs(delta[~active]) > 0.005) or teleop.velocity.any()):
            raise AssertionError(f"未通过方向验收：{keys}，实际位移 {delta}")
        rows.append(("+".join(keys), *delta))

    env.reset()
    teleop = PandaTeleop(env)
    stationary = np.zeros(3)

    def width():
        return float(env.qpos[7:9].sum())

    opened = width()
    for _ in range(75):
        teleop.step(stationary, gripper_key_down=True)
    closed = width()
    teleop.step(stationary)
    for _ in range(75):
        teleop.step(stationary, gripper_key_down=True)
    reopened = width()
    if not (opened > .06 and closed < .01 and reopened > .06 and teleop.gripper_open):
        raise AssertionError("夹爪开合或长按保持未达标")
    with (output / "controls.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(("keys", "delta_x_m", "delta_y_m", "delta_z_m"))
        writer.writerows(rows)
    print(f"六方向及组合验收通过。夹爪开度 {opened*1000:.1f} → {closed*1000:.1f} → {reopened*1000:.1f} mm。")


def check_rotations(env, output):
    rows = []
    stationary = np.zeros(3)
    for key, axis in KEY_ROTATIONS.items():
        env.reset()
        teleop = PandaTeleop(env)
        start = env.tcp_xyz
        initial_rotation = teleop.rotation.copy()
        direction = read_direction(lambda pressed: pressed == key, KEY_ROTATIONS)
        for _ in range(25):
            teleop.step(stationary, angular_direction=direction)
        for _ in range(100):
            teleop.step(stationary)
        actual = env.data.site("tcp").xmat.reshape(3, 3).copy()
        angles = np.rad2deg(orientation_error(initial_rotation, actual))
        drift = np.linalg.norm(env.tcp_xyz - start) * 1000
        for _ in range(25):
            teleop.step(stationary)
        settled = env.data.site("tcp").xmat.reshape(3, 3)
        if (np.dot(angles, axis) < 12 or np.linalg.norm(angles - 15 * direction) > 3
                or drift > 8 or np.linalg.norm(orientation_error(actual, settled)) > .002):
            raise AssertionError(f"旋转未达标：{key}，{angles} deg，位移 {drift:.2f} mm")
        rows.append((key, *angles, drift))
        print(f"{key}：主轴转角 {np.dot(angles, axis):.2f}°，TCP 位移 {drift:.2f} mm")
    with (output / "rotations.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(("key", "rotvec_x_deg", "rotvec_y_deg", "rotvec_z_deg", "tcp_drift_mm"))
        writer.writerows(rows)

    teleop.step(np.array([1, 0, 0]), gripper_key_down=True)
    target, rotation = teleop.target.copy(), teleop.rotation.copy()
    teleop.step(stationary, gripper_key_down=True, clear=True)
    if (teleop.velocity.any() or not teleop.gripper_open or
            not np.array_equal(teleop.target, target) or not np.array_equal(teleop.rotation, rotation)):
        raise AssertionError("清除指令后应保持位姿目标并恢复张开命令")


def run_check(teleop, output):
    """在真实 MuJoCo 物理步中注入按键状态并记录末端响应。"""
    initial = teleop.env.tcp_xyz
    rows = []
    steps_per_second = teleop.env.control_hz
    for tick in range(3 * steps_per_second):
        pressed = tick < steps_per_second // 2
        teleop.step(read_direction(lambda key: key == "Q" and pressed))
        x, y, z = teleop.env.tcp_xyz
        rows.append((round((tick + 1) * teleop.dt, 6), int(pressed), teleop.velocity[2],
                     teleop.target[2], x, y, z))
    output.mkdir(parents=True, exist_ok=True)
    with (output / "lift.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(("time_s", "held", "command_vz_m_s", "target_z_m",
                         "tcp_x_m", "tcp_y_m", "tcp_z_m"))
        writer.writerows(rows)

    held = np.array(rows[steps_per_second // 2 - 1][-3:])
    final = teleop.env.tcp_xyz
    drift = np.linalg.norm(final[:2] - initial[:2])
    stopped = np.ptp(np.array(rows[-25:])[:, -3:], axis=0).max()
    if (held[2] - initial[2] < 0.015 or final[2] - initial[2] < 0.03 or
            drift > 0.005 or teleop.velocity.any() or stopped > 0.001):
        raise AssertionError(f"抬升或停稳未达标，请检查 {output / 'lift.csv'}")
    print(f"按住 0.50 s 抬升 {(held[2] - initial[2]) * 1000:.1f} mm，"
          f"最终抬升 {(final[2] - initial[2]) * 1000:.1f} mm。"
          f"横向偏差 {drift * 1000:.2f} mm，最后 0.50 s 位移波动 {stopped * 1000:.3f} mm。")
    print(f"记录：{output / 'lift.csv'}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--human", action="store_true", help="打开键盘遥操窗口")
    mode.add_argument("--check", action="store_true", help="验收平移、旋转、停稳和夹爪开合")
    mode.add_argument("--smoke-test", action="store_true", help="打开图形窗口约两秒，验证渲染后自动关闭")
    parser.add_argument("--output", type=Path, default=Path("outputs/week11"))
    args = parser.parse_args(argv)
    with make_env() as env:
        teleop = PandaTeleop(env)
        if args.check:
            run_check(teleop, args.output)
            check_full_controls(env, args.output)
            check_rotations(env, args.output)
        else:
            run_window(teleop, duration=2.0 if args.smoke_test else None)


if __name__ == "__main__":
    main()

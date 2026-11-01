"""实时显示正在推进的物理状态；关闭窗口以中止未完成任务。"""
import math
import time


class ViewerClosed(Exception):
    """用户在任务完成前关闭了窗口。"""


class LiveViewer:
    def __init__(self, env, enabled=False, speed=1.):
        if not math.isfinite(speed) or speed <= 0:
            raise ValueError("speed must be positive and finite")
        self.env, self.enabled, self.speed = env, enabled, speed
        self.handle = None

    def __enter__(self):
        if self.enabled:
            import mujoco.viewer
            self.handle = mujoco.viewer.launch_passive(self.env.model, self.env.data)
            try:
                with self.handle.lock():
                    self.handle.cam.type = mujoco.mjtCamera.mjCAMERA_FIXED
                    self.handle.cam.fixedcamid = self.env.model.camera("demo").id
                    self.handle.opt.geomgroup[3] = 0
                self.handle.sync()
            except BaseException:
                self.handle.close()
                raise
            self.deadline = time.monotonic()
            self.last_sim_time = float(self.env.data.time)
            print(f"实时窗口：{self.speed:g}x 速度；关闭窗口可中止任务。", flush=True)
        return self

    def after_step(self):
        if self.handle is None:
            return
        if not self.handle.is_running():
            raise ViewerClosed()
        sim_time = float(self.env.data.time)
        # 长时间保存图像后不突发追赶；性能不足时实际速度可能低于设定值。
        self.deadline = max(self.deadline + (sim_time-self.last_sim_time)/self.speed, time.monotonic())
        self.last_sim_time = sim_time
        self.handle.sync()
        while time.monotonic() < self.deadline:
            if not self.handle.is_running():
                raise ViewerClosed()
            time.sleep(min(.02, max(0., self.deadline-time.monotonic())))
            self.handle.sync()

    def finish(self, seconds=2.):
        if self.handle is None:
            return
        print("任务完成；最终画面保留2秒，可直接关闭窗口。", flush=True)
        end = time.monotonic()+seconds
        while self.handle.is_running() and time.monotonic() < end:
            self.handle.sync()
            time.sleep(min(.02, max(0., end-time.monotonic())))

    def __exit__(self, *_):
        if self.handle is not None:
            self.handle.close()

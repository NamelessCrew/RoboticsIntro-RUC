"""规划器只产生笛卡尔位置轨迹，不读取仿真、相机或关节状态。"""
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class PlannerConfig:
    dt: float = .02
    speed: float = .08


class LinearPlanner:
    def __init__(self, config=PlannerConfig()):
        if config.dt <= 0 or config.speed <= 0 or not np.isfinite([config.dt, config.speed]).all():
            raise ValueError("planner dt and speed must be positive finite numbers")
        self.config = config

    def plan(self, start, goal):
        start, goal = np.asarray(start, float), np.asarray(goal, float)
        if start.shape != (3,) or goal.shape != (3,) or not np.isfinite([start, goal]).all():
            raise ValueError("start/goal must be finite xyz vectors")
        n = max(1, int(np.ceil(np.linalg.norm(goal-start)/(self.config.speed*self.config.dt))))
        return start + np.linspace(0, 1, n+1)[1:, None]*(goal-start)

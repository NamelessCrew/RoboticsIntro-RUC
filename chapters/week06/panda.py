"""Panda 原生 MuJoCo 入口；7 臂关节 + 2 手指，8 路执行器。"""
from .scene import RobotEnv


class PandaBasicEnv(RobotEnv):
    def __init__(self, **kwargs):
        super().__init__(robot="panda", **kwargs)

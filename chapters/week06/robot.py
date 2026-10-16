"""复用 ManiSkill 的 SO100 控制器，只指定课程目录中的可编辑 URDF。"""
from pathlib import Path

from mani_skill.agents.registration import register_agent
from mani_skill.agents.robots.so100.so_100 import SO100


@register_agent()
class SO100Robot(SO100):
    # uid 是框架注册名；正常场景使用内置 so100，URDF 对照使用 so100_custom。
    # 继承 SO100 保留关节顺序、PD 参数和夹爪定义，避免重复维护控制器。
    uid = "so100_custom"
    urdf_path = str(Path(__file__).parent / "assets/so100/so100.urdf")

"""导入/资源检查不创建 OpenGL 上下文；scene 才检验渲染。"""
import importlib.metadata
import platform
import sys

from chapters.week06.robot import PANDA_DIR, SO100_DIR
from chapters.week06.scene import RobotEnv


def main():
    print(f"Python {platform.python_version()}, {platform.system()} {platform.machine()}")
    if sys.version_info[:2] not in ((3, 11), (3, 12)):
        raise SystemExit("课程支持的解释器版本为 Python 3.11/3.12")
    for package in ("mujoco", "numpy", "pillow"):
        print(f"{package}=={importlib.metadata.version(package)}")
    assert (PANDA_DIR/"LICENSE").is_file() and (SO100_DIR/"LICENSE").is_file()
    for robot, nq, nu in (("panda", 9, 8), ("so100", 6, 6)):
        with RobotEnv(robot=robot) as env:
            assert (env.model.nq, env.model.nu) == (nq, nu)
            print(f"{robot}: model loaded, qpos={nq}, action={nu}")
    print("导入与本地模型检查通过；图像渲染尚未检查，请运行 python run.py scene。")


if __name__ == "__main__":
    main()

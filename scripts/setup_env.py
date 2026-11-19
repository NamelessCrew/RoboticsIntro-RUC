"""跨平台创建 .venv；在仓库根运行 py -3.11 scripts/setup_env.py 或 python3.11 ...。"""
from pathlib import Path
import struct
import subprocess
import sys
import venv
import shutil

ROOT = Path(__file__).resolve().parents[1]
SUPPORTED = ((3, 11), (3, 12))


def supported_python():
    """系统默认 Python 较新时，查找学生已经安装的课程版本。"""
    candidates = [("python3.11",), ("python3.12",)]
    if sys.platform == "win32":
        candidates = [("py", "-3.11"), ("py", "-3.12")] + candidates
    probe = "import sys,struct; sys.exit(0 if sys.version_info[:2] in ((3,11),(3,12)) and struct.calcsize('P') == 8 else 1)"
    for command in candidates:
        if shutil.which(command[0]) and subprocess.run(
            [*command, "-c", probe], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        ).returncode == 0:
            return command
    return None


def main():
    if sys.version_info[:2] not in SUPPORTED or struct.calcsize("P") != 8:
        command = supported_python()
        if command:
            print("切换到已安装的课程 Python：" + " ".join(command), flush=True)
            raise SystemExit(subprocess.call([*command, str(Path(__file__).resolve())]))
        raise SystemExit("请先安装 64 位 Python 3.11 或 3.12。安装后重新运行 setup.cmd (Windows) 或 bash setup.sh (macOS/Linux)。")
    directory = ROOT/".venv"
    python = directory/("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not directory.exists():
        venv.EnvBuilder(with_pip=True, symlinks=sys.platform != "win32").create(directory)
    if not python.exists():
        raise SystemExit(".venv 已存在但不是当前平台环境，请先将其改名备份，再重试。")
    subprocess.run([str(python), "-c", "import sys; assert sys.version_info[:2] in ((3,11),(3,12)), '旧 .venv 请先改名备份'"], check=True)
    subprocess.run([str(python), "-m", "pip", "install", "--only-binary=:all:", "-r", str(ROOT/"requirements.txt")], check=True)
    subprocess.run([str(python), "-m", "pip", "check"], check=True)
    subprocess.run([str(python), "-m", "scripts.doctor"], cwd=ROOT, check=True)
    print("安装完成。键盘遥操：Windows 运行 .\\run.cmd teleop --human；macOS/Linux 运行 bash run.sh teleop --human。")
    print("自动验收：将 --human 换成 --check。图形自检：换成 --smoke-test，会自动关闭窗口。")


if __name__ == "__main__":
    main()

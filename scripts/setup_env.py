"""跨平台创建 .venv；在仓库根运行 py -3.11 scripts/setup_env.py 或 python3.11 ...。"""
from pathlib import Path
import struct
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]


def main():
    if sys.version_info[:2] not in ((3, 11), (3, 12)) or struct.calcsize("P") != 8:
        raise SystemExit("请用 64 位 Python 3.11 或 3.12。Windows: py -3.11 scripts/setup_env.py；macOS/Linux: python3.11 scripts/setup_env.py")
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
    print("安装完成：python run.py scene，然后 python run.py suite")


if __name__ == "__main__":
    main()

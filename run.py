"""无需激活虚拟环境的跨平台入口；用标准库启动本仓库 .venv 中的课程程序。"""
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    command = args.pop(0) if args and not args[0].startswith("-") else "scene"
    python = ROOT/".venv"/("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not python.is_file():
        raise SystemExit("未找到 .venv。先按 README 安装：py -3.11 scripts/setup_env.py (Windows) 或 python3.11 scripts/setup_env.py (macOS/Linux)。")
    environment = None
    if "--human" in args and sys.platform == "darwin":
        # Standalone CPython may link libpython relative to its executable.
        # mjpython's trampoline runs in an app bundle; preserve the real base lib.
        base_lib = Path(subprocess.check_output([str(python), "-c", "import sys; from pathlib import Path; print(Path(sys.base_prefix)/'lib')"], text=True).strip())
        if any(base_lib.glob("libpython*.dylib")):
            environment = os.environ.copy()
            previous = environment.get("DYLD_FALLBACK_LIBRARY_PATH", "/usr/local/lib:/usr/lib")
            environment["DYLD_FALLBACK_LIBRARY_PATH"] = str(base_lib) + (":"+previous if previous else "")
        python = ROOT/".venv/bin/mjpython"
    if command == "doctor":
        target = ["-m", "scripts.doctor", *args]
    elif command == "test":
        target = ["-m", "unittest", "discover", "-s", "tests", "-v", *args]
    elif command == "python":
        target = args
    elif command in ("grasp", "vision-grasp"):
        target = ["-m", "chapters.week07.grasp", "--mode", "vision" if command == "vision-grasp" else "known", *args]
    else:
        target = ["-m", "chapters.week06.experiments", command, *args]
    return subprocess.call([str(python), *target], cwd=ROOT, env=environment)


if __name__ == "__main__":
    raise SystemExit(main())

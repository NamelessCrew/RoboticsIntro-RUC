@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo 请先运行 setup.cmd 安装课程环境。
    exit /b 1
)
".venv\Scripts\python.exe" run.py %*
exit /b %errorlevel%

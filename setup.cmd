@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto plain_python
py -3.11 -c "pass" >nul 2>nul
if errorlevel 1 goto python312
py -3.11 scripts\setup_env.py
exit /b %errorlevel%
:python312
py -3.12 -c "pass" >nul 2>nul
if errorlevel 1 goto plain_python
py -3.12 scripts\setup_env.py
exit /b %errorlevel%
:plain_python
where python >nul 2>nul
if errorlevel 1 goto missing
python scripts\setup_env.py
exit /b %errorlevel%
:missing
echo 请先安装 64 位 Python 3.11 或 3.12，再运行 setup.cmd。
exit /b 1

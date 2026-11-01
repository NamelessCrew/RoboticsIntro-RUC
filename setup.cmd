@echo off
cd /d "%~dp0"
py -3.11 scripts\setup_env.py
exit /b %errorlevel%

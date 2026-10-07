@echo off
REM Double-click or run from cmd: installs FinLit into .venv
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
pause

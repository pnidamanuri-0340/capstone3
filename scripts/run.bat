@echo off
REM Double-click or run from cmd: starts the FinLit web app
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" %*

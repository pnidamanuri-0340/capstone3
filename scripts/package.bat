@echo off
REM Builds dist\finlit.zip to copy to another computer.
REM Add --include-data to also copy saved profiles, chat history and the vector store.
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" scripts\package.py %*
) else (
    py -3 scripts\package.py %*
)
pause

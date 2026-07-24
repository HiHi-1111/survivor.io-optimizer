@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  set "PYTHON=.venv\Scripts\python.exe"
) else (
  set "PYTHON=python"
)

%PYTHON% -m app.browser_runner
if errorlevel 1 (
  echo.
  echo The optimizer could not start. Confirm Python and project dependencies are installed.
  pause
)

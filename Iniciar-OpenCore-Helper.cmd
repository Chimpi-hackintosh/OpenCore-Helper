@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Crie o ambiente de desenvolvimento antes de iniciar / Create the development environment first
  echo py -3.12 -m venv .venv
  echo .venv\Scripts\python -m pip install -r requirements.txt
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" "%~dp0main.py" %*

@echo off
chcp 65001 >nul
cd /d "%~dp0"
"..\.venv\Scripts\python.exe" main.py
if errorlevel 1 (
  echo.
  echo ===== O programa fechou com erro. Tire um print desta tela. =====
  pause
)

@echo off
chcp 65001 >nul
cd /d "%~dp0"
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=..\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Ambiente nao encontrado. Rode antes "Preparar ambiente.bat".
  pause
  exit /b 1
)
"%PY%" main.py
if errorlevel 1 (
  echo.
  echo ===== O programa fechou com erro. Tire um print desta tela. =====
  pause
)

@echo off
chcp 65001 >nul
cd /d "%~dp0"

rem Usa a venv local (.venv) e, se nao houver, a da raiz (..\.venv).
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=..\.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Ambiente nao encontrado. Rode antes "Preparar ambiente.bat".
  pause
  exit /b 1
)

echo Garantindo o PyInstaller...
"%PY%" -m pip install --quiet --disable-pip-version-check pyinstaller

rem Inclui a extensao NopeCHA no .exe SO se ela existir (vendor/ e opcional).
set "VENDOR="
if exist "vendor\nopecha_ext\manifest.json" set VENDOR=--add-data "vendor;vendor"

echo.
echo Gerando o executavel "Puxador de Certidoes"...
echo (pode levar alguns minutos)
echo.
"%PY%" -m PyInstaller --noconfirm --windowed --onefile ^
  --name "Puxador de Certidoes" ^
  --icon "..\assets\icone.ico" ^
  --collect-all playwright ^
  --collect-all customtkinter ^
  --collect-all fpdf ^
  --collect-all PIL ^
  --collect-all ddddocr ^
  --collect-all onnxruntime ^
  %VENDOR% ^
  --add-data "assets;assets" ^
  main.py
echo.
echo Pronto! O executavel esta em: dist\Puxador de Certidoes.exe
pause

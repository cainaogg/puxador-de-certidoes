@echo off
chcp 65001 >nul
rem Roda a partir da pasta "Projeto Original" (um nivel acima desta).
cd /d "%~dp0.."

set "PY=..\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo Ambiente nao encontrado. Rode antes "Preparar ambiente.bat".
  pause
  exit /b 1
)

echo Garantindo PyInstaller...
"%PY%" -m pip install --quiet --disable-pip-version-check pyinstaller

set "VENDOR="
if exist "vendor\nopecha_ext\manifest.json" set VENDOR=--add-data "vendor;vendor"

echo.
echo Gerando o executavel da NOVA interface (Edge modo-app)...
echo (pode levar alguns minutos)
echo.
"%PY%" -m PyInstaller --noconfirm --clean --windowed --onefile ^
  --name "Puxador de Certidoes" ^
  --icon "..\assets\icone.ico" ^
  --paths . ^
  --collect-all playwright ^
  --collect-all fpdf ^
  --collect-all PIL ^
  --collect-all ddddocr ^
  --collect-all onnxruntime ^
  --collect-all eel ^
  --collect-all bottle_websocket ^
  %VENDOR% ^
  --add-data "interface_web;interface_web" ^
  "interface_web\main_web.py"
echo.
echo Pronto! O executavel esta em: dist\Puxador de Certidoes.exe
pause

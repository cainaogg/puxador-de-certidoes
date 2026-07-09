@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Gerando o executavel "Puxador de Certidoes"...
echo (pode levar alguns minutos)
echo.
"..\.venv\Scripts\python.exe" -m PyInstaller --noconfirm --windowed --onefile ^
  --name "Puxador de Certidoes" ^
  --icon "..\assets\icone.ico" ^
  --collect-all playwright ^
  --collect-all customtkinter ^
  --collect-all fpdf ^
  --collect-all PIL ^
  --add-data "vendor;vendor" ^
  --add-data "assets;assets" ^
  main.py
echo.
echo Pronto! O executavel esta em: dist\Puxador de Certidoes.exe
pause

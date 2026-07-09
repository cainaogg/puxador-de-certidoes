@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   Preparando o Puxador de Certidoes
echo ============================================
echo.
echo [1/4] Criando ambiente virtual (.venv)...
python -m venv .venv
if not exist ".venv\Scripts\python.exe" (
  echo.
  echo ERRO: nao consegui criar a venv. Instale o Python 3.14+ e tente de novo.
  pause
  exit /b 1
)
set "PY=.venv\Scripts\python.exe"
echo.
echo [2/4] Instalando dependencias...
"%PY%" -m pip install --upgrade pip
"%PY%" -m pip install -r requirements.txt
echo.
echo [3/4] Baixando a extensao NopeCHA (resolve captchas)...
"%PY%" baixar_nopecha.py
echo.
echo [4/4] Instalando o navegador do Playwright (reserva)...
"%PY%" -m playwright install chromium
echo.
echo ============================================
echo   Pronto! Para abrir, rode "Iniciar.bat".
echo ============================================
pause

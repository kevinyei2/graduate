@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv (
  echo 第一次執行，正在建立環境...
  python -m venv .venv || (echo 找不到 Python，請先安裝 https://www.python.org/downloads/ & pause & exit /b 1)
)
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
python app.py
pause

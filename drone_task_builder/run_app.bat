@echo off
setlocal

cd /d %~dp0

python app.py
if errorlevel 1 (
    echo.
    echo App start failed.
    echo Try:
    echo python -m pip install -r requirements.txt
    pause
    exit /b 1
)

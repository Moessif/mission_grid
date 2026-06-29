@echo off
setlocal

cd /d %~dp0

python -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo Dependency install failed.
    pause
    exit /b 1
)

python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --name DroneTaskBuilder ^
  --windowed ^
  app.py

if errorlevel 1 (
    echo.
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo Build complete: dist\DroneTaskBuilder
pause

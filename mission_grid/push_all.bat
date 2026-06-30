@echo off
echo Pushing to GitHub...
git push origin master
if %errorlevel% neq 0 (
    echo Failed to push to GitHub
    pause
    exit /b 1
)

echo Successfully pushed to GitHub!
pause
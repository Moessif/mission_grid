@echo off
echo Pushing to Gitee...
git push origin master
if %errorlevel% neq 0 (
    echo Failed to push to Gitee
    pause
    exit /b 1
)

echo Pushing to GitHub...
git push github master
if %errorlevel% neq 0 (
    echo Failed to push to GitHub
    pause
    exit /b 1
)

echo Successfully pushed to both Gitee and GitHub!
pause
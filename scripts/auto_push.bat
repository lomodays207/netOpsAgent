@echo off
:: Create a batch file to automatically add, commit, and push changes to GitHub
:: Ensure UTF-8 execution
chcp 65001 >nul

echo ==========================================
echo      自动提交代码到GitHub / Auto Push
echo ==========================================

echo [1/4] 添加所有更改 / Adding all changes...
git add .

echo [2/4] 检查状态 / Checking status...
git status

set /p commit_msg="输入提交信息 (直接回车默认为 'Auto update'): "
if "%commit_msg%"=="" set commit_msg=Auto update

echo [3/4] 提交更改: "%commit_msg%" / Committing...
git commit -m "%commit_msg%"

echo [4/4] 推送到远程仓库 / Pushing to remote...
git push

echo ==========================================
echo      完成! / Done!
echo ==========================================
pause

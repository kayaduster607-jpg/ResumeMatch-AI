@echo off
cd /d %~dp0
if exist backend\.job_browser rmdir /s /q backend\.job_browser
echo 已删除 backend\.job_browser，请重新启动后端并打开浏览器登录。
pause

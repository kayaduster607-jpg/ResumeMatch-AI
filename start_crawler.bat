@echo off
chcp 65001 >nul
set PYTHONUTF8=1
echo ResumeMatch-AI 岗位爬虫交互启动器
echo.
python -m job_crawler
if errorlevel 1 (
  echo.
  echo 运行失败。若是浏览器启动失败，请先执行：python -m playwright install chromium
)
pause

@echo off
cd /d %~dp0
cd backend
python -c "from app.services.playwright_browser_worker import get_browser_worker; get_browser_worker().open_login_pages(['boss','zhaopin','liepin','qiancheng']); print('已打开项目专用 Edge。登录完成后回到网页操作。')"
pause

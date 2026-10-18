@echo off
chcp 65001 >nul
cd /d %~dp0

echo [1/4] 创建 Python 虚拟环境...
cd backend
if not exist .venv python -m venv .venv
call .venv\Scripts\activate

echo [2/4] 安装后端依赖...
pip install -r requirements.txt

echo [3/4] 安装 Playwright Chromium 浏览器...
python -m playwright install chromium

cd ..\frontend

echo [4/4] 安装前端依赖并构建...
npm install
npm run build

echo.
echo 安装完成。请分别运行 start_backend.bat 和 start_frontend.bat。
pause

#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
python -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
python -m playwright install chromium
cd frontend
npm install
npm run build
echo "安装完成。分别运行 ./start_backend.sh 和 ./start_frontend.sh"

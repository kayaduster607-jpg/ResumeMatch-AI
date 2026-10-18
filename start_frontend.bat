@echo off
chcp 65001 >nul
cd /d %~dp0\frontend
npm run dev
pause

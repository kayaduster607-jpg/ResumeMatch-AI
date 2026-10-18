@echo off
chcp 65001 >nul
cd /d %~dp0\backend
if exist .venv\Scripts\activate call .venv\Scripts\activate
python main.py
pause

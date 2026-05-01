@echo off
cd /d "%~dp0"
title LINE Bot Launcher

echo =============================================
echo  LINE Bot Auto-Start
echo =============================================

.venv\Scripts\python.exe start_all.py

pause

@echo off
chcp 936 >nul
title Huanqiu Rescue - Grab Ticket
cd /d "%~dp0"

:: Auto-elevate to admin (game is WeChat mini-program, MoveWindow needs admin)
net file >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting admin privileges... Please click Yes on the UAC prompt.
    powershell -NoProfile -Command "Start-Process -FilePath '%~dp0.venv27\Scripts\python.exe' -ArgumentList 'gui.py' -WorkingDirectory '%~dp0' -Verb RunAs -WindowStyle Minimized"
    exit /b
)

if not exist ".venv27\Scripts\python.exe" (
    echo [Error] venv not found: .venv27\Scripts\python.exe
    pause
    exit /b 1
)

echo Starting Huanqiu GUI...
echo.
start "" /min ".venv27\Scripts\python.exe" gui.py

echo.
echo GUI exited.
pause

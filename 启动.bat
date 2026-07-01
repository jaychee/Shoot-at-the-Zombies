@echo off
chcp 65001 >nul
title 寰球救援 - 抢票&战斗
cd /d "%~dp0"

if not exist ".venv27\Scripts\python.exe" (
    echo [错误] 未找到虚拟环境 .venv27\Scripts\python.exe
    echo 请先创建虚拟环境并安装依赖。
    pause
    exit /b 1
)

echo 正在启动寰球救援 GUI...（关闭此窗口即停止脚本）
echo.
".venv27\Scripts\python.exe" gui.py

echo.
echo GUI 已退出。
pause

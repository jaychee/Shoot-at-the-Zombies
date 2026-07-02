@echo off
chcp 65001 >nul
title 寰球救援 - 抢票&战斗
cd /d "%~dp0"

:: 自动请求管理员权限（UAC 提权）。
:: 游戏是微信小程序(WeChatAppEx.exe)，窗口受保护，必须管理员权限才能 MoveWindow
:: 调整窗口大小/位置；非管理员运行时 resize 会报「拒绝访问」导致抢票坐标全偏。
:: 通过 fltmc 检测当前是否已是管理员，不是则用 PowerShell 触发 UAC 重启自身。
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 当前非管理员权限，正在请求提权（请在弹出的 UAC 窗口点「是」）...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

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

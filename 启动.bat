@echo off
chcp 65001 >nul
title 寰球救援 - 抢票&战斗
cd /d "%~dp0"

:: 自动请求管理员权限（UAC 提权）。
:: 游戏是微信小程序(WeChatAppEx.exe)，窗口受保护，必须管理员权限才能 MoveWindow
:: 调整窗口大小/位置；非管理员运行时 resize 会报「拒绝访问」导致抢票坐标全偏。
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo 当前非管理员权限，正在请求提权（请在弹出的 UAC 窗口点「是」）...
    :: 用 PowerShell 提权，直接启动 python（避免重启 bat 自身的中文路径传参问题）
    :: -WorkingDirectory 确保提权后工作目录仍是项目目录
    powershell -NoProfile -Command "Start-Process -FilePath '%~dp0.venv27\Scripts\python.exe' -ArgumentList 'gui.py' -WorkingDirectory '%~dp0' -Verb RunAs"
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

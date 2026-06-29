@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

:: AifaQuant 每日自动刷新脚本
:: 建议用 Windows 任务计划程序每天 15:35 运行一次（A股收盘后）
:: 任务操作：启动程序 = 本 bat 文件；起始于 = 项目根目录

set "PROJECT_ROOT=%~dp0.."
cd /d "%PROJECT_ROOT%"

if not exist "data_store" mkdir "data_store"

:: Load .env file if present. Values containing '=' are preserved after the first '='.
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
        set "line=%%a"
        if not "!line:~0,1!"=="#" (
            if not "%%b"=="" set "%%a=%%b"
        )
    )
)

set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"

"%PYTHON_EXE%" scripts\daily_refresh.py >> data_store\daily_refresh.log 2>&1
endlocal
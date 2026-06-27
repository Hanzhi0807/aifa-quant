@echo off
chcp 65001 >nul
setlocal

:: AifaQuant 每日自动刷新脚本
:: 建议用 Windows 任务计划程序每天 15:35 运行一次（A股收盘后）
:: 任务操作：启动程序 = 本 bat 文件；起始于 = 项目根目录

set PROJECT_ROOT=%~dp0..
cd /d "%PROJECT_ROOT%"

call .venv\Scripts\activate.bat
python scripts\daily_refresh.py >> data_store\daily_refresh.log 2>&1

deactivate
endlocal

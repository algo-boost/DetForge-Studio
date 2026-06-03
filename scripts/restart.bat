@echo off
REM 仅重启后端（不改前端 dist）
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0restart.ps1" %*
if errorlevel 1 exit /b 1

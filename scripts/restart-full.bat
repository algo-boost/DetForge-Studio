@echo off
REM 前端 npm run build + 重启后端（改 UI 后用这个）
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0restart.ps1" -Full %*
if errorlevel 1 exit /b 1

@echo off
setlocal
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\formal_launch.ps1" -Problem 4 %*
set "run_code=%errorlevel%"
if /i "%~1"=="-Check" exit /b %run_code%
echo.
pause
exit /b %run_code%

@echo off
setlocal
chcp 65001 >nul
echo P4 practice: the loaded policy, source and SHA256 are printed below.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\practice_launch.ps1" -Problem 4 %*
set "run_code=%errorlevel%"
if /i "%~1"=="-Check" exit /b %run_code%
echo.
pause
exit /b %run_code%

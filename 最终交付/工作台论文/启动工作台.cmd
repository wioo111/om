@echo off
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0启动工作台.ps1" %*
if errorlevel 1 (
  echo.
  echo Startup failed. Please read the message above.
  pause
  exit /b 1
)

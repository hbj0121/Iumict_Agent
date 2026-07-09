@echo off
chcp 65001 >nul
title Smart Water PLC - System Stop

echo.
echo ========================================
echo   Smart Water PLC - System Stop
echo ========================================
echo.

cd /d "%~dp0"

echo Docker Container Stop...
docker-compose stop
echo Docker Stop Complete

echo.
echo Python Process Stop...
taskkill /f /im python.exe >nul 2>&1
echo Python Stop Complete

echo.
echo All Service Stop Complete.
pause
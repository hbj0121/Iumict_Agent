@echo off
title Smart Water PLC

cd /d "%~dp0"
set PYTHONPATH=%CD%

echo.
echo ========================================
echo   Smart Water PLC - System Start
echo ========================================
echo.

echo [1/3] Docker PostgreSQL Start
docker-compose up -d
echo [1/3] Docker Done
echo.

echo [2/3] Waiting ..
ping 127.0.0.1 -n 6 >nul
echo [2/3] Rdy
echo.

echo [3/3] Choose Service:
echo.
echo   1. Streamlit UI
echo   2. FastAPI Server
echo   3. Both
echo   4. Exit
echo.
set /p choice=Choose (1-4):

if "%choice%"=="1" goto run_streamlit
if "%choice%"=="2" goto run_fastapi
if "%choice%"=="3" goto run_both
if "%choice%"=="4" goto end
goto end

:run_streamlit
echo.
echo Streamlit Start: http://localhost:8501
echo.
poetry run streamlit run src/application/ui/app.py
goto end

:run_fastapi
echo.
echo FastAPI Start: http://localhost:8000/docs
echo.
poetry run python src/application/api/main.py
goto end

:run_both
echo.
start "FastAPI" cmd /k "cd /d %CD% && set PYTHONPATH=%CD% && poetry run python src/application/api/main.py"
start "Streamlit" cmd /k "cd /d %CD% && set PYTHONPATH=%CD% && poetry run streamlit run src/application/ui/app.py"
echo.
echo Both Service init complete!
echo   Streamlit : http://localhost:8501
echo   FastAPI   : http://localhost:8000/docs
echo.
pause
goto end

:end
echo.
echo Exit.
pause
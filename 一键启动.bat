@echo off
chcp 65001 >nul 2>&1
title Qingnang Startup

REM ========================================================
REM  Qingnang APP - One-click startup
REM  Skip redundant checks (DB migrated / deps installed)
REM ========================================================

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"

REM -- Pick Python: real interpreter first, skip WindowsApps alias --
set "PYTHON="
for /f "delims=" %%i in ('where python 2^>nul ^| findstr /v WindowsApps') do (
    set "PYTHON=%%i"
    goto :py_ok
)
if exist "C:\Users\macotai\python-sdk\python3.13.2\python.exe" (
    set "PYTHON=C:\Users\macotai\python-sdk\python3.13.2\python.exe"
    goto :py_ok
)
echo [ERROR] No usable Python found
pause
exit /b 1

:py_ok
echo [OK] Python: %PYTHON%

REM -- Kill port 8767 if occupied --
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8767 " ^| findstr LISTENING') do (
    echo   Freeing port 8767 PID %%p
    taskkill /F /PID %%p >nul 2>&1
)
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":5173 " ^| findstr LISTENING') do (
    echo   Freeing port 5173 PID %%p
    taskkill /F /PID %%p >nul 2>&1
)

REM -- Start backend (uvicorn directly, skip run.py pip install) --
echo.
echo [START] Backend  http://localhost:8767
start "Qingnang-Backend" /d "%BACKEND%" cmd /k "%PYTHON%" -m uvicorn app.main:app --host 0.0.0.0 --port 8767

REM -- Start frontend --
echo [START] Frontend  http://localhost:5173
start "Qingnang-Frontend" /d "%FRONTEND%" cmd /k npm run dev

echo.
echo Waiting for services...
timeout /t 6 /nobreak >nul

echo.
echo === Status ===
curl -s http://localhost:8767/health 2>nul && echo. || echo   Backend: not ready yet
echo   Frontend: http://localhost:5173/
echo ==============
echo.
echo [DONE] Services launched in separate windows.
echo   Close backend/frontend windows to stop.
echo.
pause
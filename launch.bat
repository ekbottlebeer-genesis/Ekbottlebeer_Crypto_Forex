@echo off
setlocal
title Ekbottlebeer A+ Operator - Watchdog

:LOOP_START
cls
echo ===================================================
echo   Ekbottlebeer A+ Operator - Watchdog
echo ===================================================
echo [INFO] Time: %TIME%
echo.

REM --- 1. Git Update ---
echo [WATCHDOG] Checking for updates...
git pull

REM --- 2. Python Detection & VENV ---
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
) else (
    py --version >nul 2>&1
    if %errorlevel% equ 0 (
        set PYTHON_CMD=py
    ) else (
        echo [ERROR] Python not found! Install Python 3.10+ and Add to PATH.
        pause
        exit /b 1
    )
)

echo [INFO] Detected Python Version:
%PYTHON_CMD% --version
echo.


if not exist ".venv" (
    echo [INFO] Creating Virtual Environment...
    %PYTHON_CMD% -m venv .venv
)

REM --- 3. Activation (Windows) ---
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
    echo [WATCHDOG] VENV Activated.
) else (
    echo [WARN] Venv script not found, using global python.
)

REM --- 4. Dependencies ---
echo [WATCHDOG] Checking requirements...
%PYTHON_CMD% -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies!
    pause
    exit /b 1
)

REM --- 5. Config Check ---
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo [WARN] Created .env from template. PLEASE EDIT IT!
    )
)

REM --- 6. Pre-Flight Checks ---
echo [WATCHDOG] Running System Diagnostics...
echo ---------------------------------------------------
%PYTHON_CMD% debug_mt5.py
echo ---------------------------------------------------
%PYTHON_CMD% debug_bybit_v2.py
echo ---------------------------------------------------

REM --- 7. Launch Brain ---
echo [WATCHDOG] All systems go. Starting Bot...
timeout /t 3 >nul
%PYTHON_CMD% main.py

REM --- 8. Crash Recovery ---
echo.
echo [WATCHDOG] Bot stopped or crashed.
echo [WATCHDOG] Restarting in 5 seconds...
timeout /t 5
goto :LOOP_START

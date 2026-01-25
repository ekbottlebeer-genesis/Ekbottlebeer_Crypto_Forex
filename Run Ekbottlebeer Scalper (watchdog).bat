@echo off
title The Watchdog - A+ Operator
color 0A

echo [WATCHDOG] INITIALIZING...
echo [DEBUG] If this window closes immediately, there is a system path issue.
timeout /t 2 >nul

:: --- 0. PRE-FLIGHT CHECKS ---
echo [WATCHDOG] 🔍 SYSTEM CHECK...

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Python is NOT installed or not in PATH!
    echo.
    echo Please install Python 3.10+ from python.org.
    echo IMPORTANT: Check the box "Add Python to PATH" during installation.
    echo.
    pause
    exit
)

:: --- 1. CONFIGURATION CHECK ---
if not exist ".env" (
    echo [WATCHDOG] .env file MISSING!
    if exist ".env.example" (
        echo [WATCHDOG] Creating .env from template...
        copy ".env.example" ".env" >nul
        echo.
        echo [IMPORTANT] STOP!
        echo.
        echo A new ".env" file has been created.
        echo You MUST open it now and add your API KEYS (Telegram, Bybit, MT5).
        echo.
        echo Press any key ONLY after you have saved your keys...
        pause
    ) else (
        echo [ERROR] .env.example is missing! Cannot create config.
        pause
        exit
    )
)

:loop
echo ------------------------------------
echo [WATCHDOG] Checking for updates...

:: 2. Cleanup Stale Processes
taskkill /F /IM python.exe /FI "WINDOWTITLE ne The Watchdog*" >nul 2>&1

:: 3. CODE SYNC (SAFE MODE)
:: Removed aggressive 'git reset --hard' to prevent crashing the running script.
:: Using gentle pull.
echo [WATCHDOG] Syncing with repository...
git pull

:: 4. Environment Setup (Auto-Venv)
if not exist ".venv" (
    echo [WATCHDOG] Creating Virtual Environment (.venv)...
    python -m venv .venv
)

:: Activate VENV
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
    echo [WATCHDOG] VENV Activated.
) else (
    echo [WATCHDOG] WARNING: .venv corrupt? Using global python.
)

:: 5. Install Dependencies
echo [WATCHDOG] Checking/Installing requirements...
python -m pip install -r requirements.txt --upgrade

:: 6. SYSTEM DIAGNOSTICS
echo [WATCHDOG] Running Pre-Flight Diagnostics...
echo ---------------------------------------------------
python debug_mt5.py
echo ---------------------------------------------------
python debug_bybit_v2.py
echo ---------------------------------------------------
echo [WATCHDOG] Diagnostics Complete.

:: 7. Launch The Brain
echo [WATCHDOG] 🚀 Launching Bot...
timeout /t 3
python main.py

:: 8. Crash Recovery
echo [WATCHDOG] X Bot process ended.
echo [WATCHDOG] Restarting in 5 seconds...
timeout /t 5
goto loop

pause

@echo off
title The Watchdog - A+ Operator
color 0A

:: --- 0. PRE-FLIGHT CHECKS ---
echo [%TIME%] [WATCHDOG] 🔍 SYSTEM CHECK...

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is NOT installed or not in PATH!
    echo Please install Python 3.10+ and check "Add to PATH".
    pause
    exit
)

:: --- 1. CONFIGURATION CHECK ---
if not exist ".env" (
    echo [%TIME%] [WATCHDOG] ⚠️ .env file MISSING!
    if exist ".env.example" (
        echo [%TIME%] [WATCHDOG] Creating .env from template...
        copy ".env.example" ".env" >nul
        echo.
        echo [IMPORTANT] 🛑 STOP! 🛑
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
echo [%TIME%] ------------------------------------
echo [%TIME%] [WATCHDOG] Checking for updates...

:: 2. Cleanup Stale Processes (Self-Healing)
taskkill /F /IM python.exe /FI "WINDOWTITLE ne The Watchdog*" >nul 2>&1

:: 3. Pull Latest Code (Verified Source)
echo [%TIME%] [WATCHDOG] Force-syncing with repository...
git fetch --all
git reset --hard origin/main

:: 4. Environment Setup (Auto-Venv)
if not exist ".venv" (
    echo [%TIME%] [WATCHDOG] 🔨 Creating Virtual Environment (.venv)...
    python -m venv .venv
)

:: Activate VENV
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
    echo [%TIME%] [WATCHDOG] VENV Activated.
) else (
    echo [%TIME%] [WATCHDOG] WARNING: .venv corrupt? Using global python.
)

:: 5. Install Dependencies (Visible)
echo [%TIME%] [WATCHDOG] 📦 Checking/Installing requirements...
python -m pip install -r requirements.txt --upgrade

:: 6. SYSTEM DIAGNOSTICS (PRE-FLIGHT CHECKS)
echo [%TIME%] [WATCHDOG] 🔍 Running Pre-Flight Diagnostics...
echo ---------------------------------------------------
python debug_mt5.py
echo ---------------------------------------------------
python debug_bybit_v2.py
echo ---------------------------------------------------
echo [%TIME%] [WATCHDOG] Diagnostics Complete.

:: 7. Launch The Brain
echo [%TIME%] [WATCHDOG] 🚀 Launching Bot...
timeout /t 3
python main.py

:: 8. Crash Recovery
echo [%TIME%] [WATCHDOG] ❌ Bot process ended (Crash/Exit).
echo [%TIME%] [WATCHDOG] Restarting in 5 seconds...
timeout /t 5
goto loop

pause

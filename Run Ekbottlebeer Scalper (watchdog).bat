@echo off
title The Watchdog - A+ Operator

:loop
echo [%TIME%] ------------------------------------
echo [%TIME%] [WATCHDOG] Checking for updates...

:: 1. Cleanup Stale Processes (Self-Healing)
taskkill /F /IM python.exe /FI "WINDOWTITLE ne The Watchdog*" >nul 2>&1

:: 2. Pull Latest Code (Verified Source)
git pull

:: 3. Environment Isolation (Activate VENV)
:: Assumes .venv folder exists in project root
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
    echo [%TIME%] [WATCHDOG] VENV Activated.
) else (
    echo [%TIME%] [WATCHDOG] WARNING: .venv not found! Using global python.
)

:: 4. Install Dependencies (Ensure environment is synced)
echo [%TIME%] [WATCHDOG] Checking/Installing requirements...
python -m pip install -r requirements.txt >nul 2>&1

:: 5. SYSTEM DIAGNOSTICS (PRE-FLIGHT CHECKS)
echo [%TIME%] [WATCHDOG] 🔍 Running Pre-Flight Diagnostics...
echo ---------------------------------------------------
python debug_mt5.py
echo ---------------------------------------------------
python debug_bybit_v2.py
echo ---------------------------------------------------
echo [%TIME%] [WATCHDOG] Diagnostics Complete.

:: 6. Launch The Brain
echo [%TIME%] [WATCHDOG] Launching Bot...
timout /t 3
python main.py

:: 7. Crash Recovery
echo [%TIME%] [WATCHDOG] Bot process ended. Restarting in 5 seconds...
timeout /t 5
goto loop

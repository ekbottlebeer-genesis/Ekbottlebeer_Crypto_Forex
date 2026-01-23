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
python -m pip install -r requirements.txt

:: 5. Launch The Brain
echo [%TIME%] [WATCHDOG] Launching Bot...
python main.py

:: 6. Crash Recovery
echo [%TIME%] [WATCHDOG] Bot process ended. Restarting in 5 seconds...
timeout /t 5
goto loop

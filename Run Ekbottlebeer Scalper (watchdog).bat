@echo off
title The Watchdog - A+ Operator
color 0A

echo [WATCHDOG] INITIALIZING...
echo [DEBUG] Starting up...
REM Pause here to catch immediate startup errors if any
timeout /t 1 >nul

REM --- DETECT PYTHON COMMAND ---
REM Try 'python' first
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
    goto :check_env
)

REM Try 'py' (Windows Launcher)
py --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=py
    goto :check_env
)

REM IF WE GET HERE, PYTHON IS MISSING
echo.
echo [ERROR] SYSTEM PATH ISSUE DETECTED!
echo ----------------------------------------------------
echo "python" or "py" command was not found.
echo.
echo HOW TO FIX:
echo 1. Download Python from python.org
echo 2. Run the installer
echo 3. VERY IMPORTANT: Check the box "Add Python to environment variables" or "Add to PATH"
echo 4. Restart your computer.
echo.
echo Press any key to exit...
pause
exit

:check_env
echo [WATCHDOG] Using command: %PYTHON_CMD%

REM --- 1. CONFIGURATION CHECK ---
if not exist ".env" (
    echo [WATCHDOG] .env file MISSING.
    if exist ".env.example" (
        echo [WATCHDOG] Auto-creating .env from template...
        copy ".env.example" ".env" >nul
        echo [WATCHDOG] PLEASE REMEMBER TO EDIT .env WITH YOUR KEYS!
    ) else (
        echo [WATCHDOG] No .env.example found. Skipping config creation.
    )
)

:loop
echo ------------------------------------
echo [WATCHDOG] Checking for updates...

REM 2. Cleanup Stale Processes
taskkill /F /IM python.exe /FI "WINDOWTITLE ne The Watchdog*" >nul 2>&1

REM 3. CODE SYNC (SAFE MODE)
echo [WATCHDOG] Syncing with repository...
git pull

REM 4. Environment Setup (Auto-Venv)
if not exist ".venv" (
    echo [WATCHDOG] Creating Virtual Environment (.venv)...
    %PYTHON_CMD% -m venv .venv
)

REM Activate VENV
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
    echo [WATCHDOG] VENV Activated.
) else (
    echo [WATCHDOG] WARNING: .venv corrupt? Using global python.
)

REM 5. Install Dependencies
echo [WATCHDOG] Checking/Installing requirements...
%PYTHON_CMD% -m pip install -r requirements.txt --upgrade

REM 6. SYSTEM DIAGNOSTICS
echo [WATCHDOG] Running Pre-Flight Diagnostics...
echo ---------------------------------------------------
%PYTHON_CMD% debug_mt5.py
echo ---------------------------------------------------
%PYTHON_CMD% debug_bybit_v2.py
echo ---------------------------------------------------
echo [WATCHDOG] Diagnostics Complete.

REM 7. Launch The Brain
echo [WATCHDOG] Launching Bot...
timeout /t 3
%PYTHON_CMD% main.py

REM 8. Crash Recovery
echo [WATCHDOG] X Bot process ended.
echo [WATCHDOG] Restarting in 5 seconds...
timeout /t 5
goto loop

pause

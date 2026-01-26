@echo off
title Manual Debug Run
echo [DEBUG] Manual Launch - Window will stay open.
echo.

echo [DEBUG] 1. Activating VENV...
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else (
    echo [ERROR] VENV not found. Running global python...
)

echo.
echo [DEBUG] 2. Checking Dependencies...
python -m pip install -r requirements.txt

echo.
echo [DEBUG] 3. Running Diagnostics...
python debug_mt5.py
python debug_bybit_v2.py
python debug_session.py

echo.
echo [DEBUG] 4. Launching Main Bot...
python main.py

echo.
echo [DEBUG] Bot finished.
pause

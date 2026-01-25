@echo off
setlocal
cd /d "%~dp0"

echo ===================================================
echo   Ekbottlebeer A+ Operator - Launcher
echo ===================================================
echo.
echo [INFO] Starting up...
echo.

REM --- 1. Python Detection ---
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
    goto :FOUND_PYTHON
)

py --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=py
    goto :FOUND_PYTHON
)

echo [ERROR] Python not found! 
echo Please install Python 3.10+ and check "Add to PATH".
echo.
pause
exit /b 1

:FOUND_PYTHON
echo [INFO] Using Python: %PYTHON_CMD%

REM --- 2. VENV Setup ---
if not exist ".venv" (
    echo [INFO] Creating Virtual Environment...
    %PYTHON_CMD% -m venv .venv
)

REM --- 3. Activation ---
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
) else (
    echo [WARN] Venv script not found, using global python.
)

REM --- 4. Dependencies ---
echo [INFO] Checking dependencies...
%PYTHON_CMD% -m pip install -r requirements.txt --quiet

REM --- 5. Config Check ---
if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo [WARN] Created .env from template. PLEASE EDIT IT!
    )
)

REM --- 6. Launch ---
echo.
echo [INFO] Launching Bot...
echo ===================================================
%PYTHON_CMD% main.py
echo ===================================================
echo [INFO] Bot stopped.
pause

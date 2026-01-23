#!/bin/bash
echo "The Watchdog - A+ Operator"

while true; do
    echo "[$(date)] ------------------------------------"
    echo "[$(date)] [WATCHDOG] Checking for updates..."

    # 1. Pull Latest Code
    git pull

    # 2. Environment Isolation (Activate VENV)
    if [ -d ".venv" ]; then
        source .venv/bin/activate
        echo "[$(date)] [WATCHDOG] VENV Activated."
    else
        echo "[$(date)] [WATCHDOG] WARNING: .venv not found! Using global python."
    fi

    # 3. Install Dependencies
    echo "[$(date)] [WATCHDOG] Checking requirements..."
    pip install -r requirements.txt > /dev/null 2>&1

    # 4. SYSTEM DIAGNOSTICS
    echo "[$(date)] [WATCHDOG] 🔍 Running Pre-Flight Checks..."
    echo "---------------------------------------------------"
    python debug_mt5.py
    echo "---------------------------------------------------"
    python debug_bybit_v2.py
    echo "---------------------------------------------------"
    echo "[$(date)] [WATCHDOG] Checks Complete. Starting Brain..."
    sleep 3

    # 5. Launch The Brain
    python main.py

    # 6. Crash Recovery
    echo "[$(date)] [WATCHDOG] Bot process ended. Restarting in 5 seconds..."
    sleep 5
done

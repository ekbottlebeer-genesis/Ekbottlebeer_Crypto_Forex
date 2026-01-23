#!/bin/bash

# Title: The Watchdog - A+ Operator (Mac/Linux)
echo "🦅 Starting The Ekbottlebeer Watchdog..."

while true; do
    echo "------------------------------------"
    echo "[$(date +'%T')] [WATCHDOG] Checking for updates..."

    # 1. Pull Latest Code
    git pull

    # 2. Environment Activation
    if [ -d ".venv" ]; then
        source .venv/bin/activate
        echo "[$(date +'%T')] [WATCHDOG] VENV Activated."
    else
        echo "[$(date +'%T')] [WATCHDOG] WARNING: .venv not found. Using global python."
    fi

    # 3. Install Dependencies (Quietly)
    echo "[$(date +'%T')] [WATCHDOG] Syncing dependencies..."
    pip install -r requirements.txt > /dev/null 2>&1

    # 4. Launch The Brain
    echo "[$(date +'%T')] [WATCHDOG] Launching Bot..."
    python3 main.py

    # 5. Crash Recovery
    EXIT_CODE=$?
    echo "[$(date +'%T')] [WATCHDOG] Bot process ended (Code: $EXIT_CODE). Restarting in 5 seconds..."
    sleep 5
done

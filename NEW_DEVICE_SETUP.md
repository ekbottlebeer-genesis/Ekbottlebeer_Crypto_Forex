# 🚀 New Device Setup Guide
**The Ekbottlebeer A+ Operator Deployment Manual**

This guide details how to set up the bot from scratch on a completely new device (Windows VPS or Local Machine).

> **Recommendation**: For production trading with MetaTrader 5, a **Windows VPS** is highly recommended for 24/7 uptime and native MT5 support.

---

## 1. Prerequisites (Install These First)

### A. System Requirements
- **OS**: Windows 10/11 or Windows Server 2019+ (Preferred for MT5).
  - *Mac Users*: Can run in development mode, but MT5 bridge requires `MetaTrader5` python package which is Windows-optimized. (Mac setup is possible but requires WINE or Parallels for the actual terminal, though the Python library is Windows-only for standard usage. **Mac users should use the Mock mode or a Windows VM.**)
- **RAM**: Minimum 4GB (8GB Recommended).

### B. Software
1.  **Git**: Download from [git-scm.com](https://git-scm.com/downloads).
    - *During install*: Select "Use Git from the Windows Command Prompt".
2.  **Python 3.10+**: Download from [python.org](https://www.python.org/downloads/).
    - **CRITICAL**: Check the box **"Add Python to PATH"** during installation.
3.  **MetaTrader 5 (MT5)**: Download from your broker (e.g., Pepperstone, IC Markets).
    - Install and **Login** to your trading account.
    - **Enable Auto-Trading**: Go to `Tools` -> `Options` -> `Expert Advisors` -> Check `Allow automated trading`.

---

## 2. Project Installation

### Step 1: Clone the Repository
Open a terminal (Command Prompt or PowerShell) and run:

```bash
# Navigate to where you want the bot (e.g., Desktop)
cd Desktop

# Clone the repo (Replace URL with your actual repo URL if private)
git clone <YOUR_REPO_URL>

# Enter the directory
cd "Ekbottlebeer Scalper Crypto and Forex"
```

### Step 2: Create Virtual Environment
Isolate dependencies to avoid conflicts.

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**Mac/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```
*(You will see `(.venv)` appear at the start of your command line.)*

### Step 3: Install Dependencies
Run the auto-install command:
```bash
pip install -r requirements.txt
```
*Note: If `mplfinance` fails, try `pip install --upgrade pip` first.*

---

## 3. Configuration (The Secrets)

You need to create a `.env` file to store your API keys and passwords. This file is ignored by Git for security.

1.  Create a new file named `.env` in the project root folder.
2.  Paste the following template and fill in your details:

```ini
# --- TELEGRAM SETTINGS ---
# Get these from @BotFather and @userinfobot
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
TELEGRAM_SIGNAL_CHANNEL_ID=your_channel_id_here

# --- BYBIT SETTINGS (Crypto) ---
# Set BYBIT_DEMO=True for practice
BYBIT_API_KEY=your_bybit_key
BYBIT_API_SECRET=your_bybit_secret
BYBIT_DEMO=True
BYBIT_TESTNET=False

# --- METATRADER 5 SETTINGS (Forex) ---
# Ensure these match exactly what is in MT5 -> File -> Login to Trade Account
MT5_LOGIN=12345678
MT5_PASSWORD=your_mt5_password
MT5_SERVER=Pepperstone-Demo
```

---

## 4. Running the Bot

### Option A: Manual Start (Development/Testing)
Ensure your `.venv` is active, then run:

```bash
python main.py
```

### Option B: Auto-Healing Mode (Production)
Use the included batch file that auto-Restarts the bot if it crashes and auto-updates code from Git.

1.  Double-click `Run Ekbottlebeer Scalper (watchdog).bat`
2.  Or run in terminal:
    ```bash
    "Run Ekbottlebeer Scalper (watchdog).bat"
    ```

---

## 5. Verification Checklist

- [ ] **Telegram**: Did you get a "System Initializing" message?
- [ ] **MT5**: Did the console say `✅ MT5 Bridge Connected`?
- [ ] **Bybit**: Did the console say `✅ Bybit Bridge Initialized`?
- [ ] **Test**: Type `/status` in Telegram to check health.

> **Troubleshooting**: If MT5 fails to connect, ensure the Terminal is OPEN and running, and `Algo Trading` is Green/Enabled at the top toolbar.

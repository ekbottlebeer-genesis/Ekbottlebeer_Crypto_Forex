# 🦅 The Ekbottlebeer A+ Operator
**"The Eye, The Brain, The Hand, The Mouth"**

> **Current Status**: 🟢 LIVE / DEMO READY
> **Version**: 1.0.0 (First Release)

## 🏗 System Architecture

The bot is designed as a modular organism, adhering to the "Eye, Brain, Hand, Mouth" philosophy for robustness and clarity.

### 👁 The Eye (Monitoring)
**Goal**: See the market with absolute clarity.
- **Bridges**: 
  - `src/bridges/mt5_bridge.py`: Connects to **MetaTrader 5** for Forex/Indices/Commodities active sessions (Asia/London/NY).
  - `src/bridges/bybit_bridge.py`: Connects to **Bybit Unified Trading** for 24/7 Crypto perpetuals.
- **Data**: Fetches **50-Candle** High Timeframe (1H) context and **200-Candle** Low Timeframe (5m) structure.

### 🧠 The Brain (Logic)
**Goal**: Process data and make high-probability decisions.
- **Strategy** (`src/strategy/smc_logic.py`):
  1.  **HTF Sweep Filter**: Detects liquidity sweeps on the 1H timeframe (50-bar lookback).
  2.  **LTF MSS**: Waits for a Market Structure Shift on the 5m timeframe (must occur within 1 hour).
  3.  **FVG Entry**: Hunts for Fair Value Gaps in **Discount** (for Longs) or **Premium** (for Shorts).
- **Risk Guardrails** (`src/risk/guardrails.py`):
  - **30/30 News Rule**: Avoids trading 30 mins before/after Red Folder events.
  - **Session Lock**: Pauses trading if Max Session Loss is hit.

### ✋ The Hand (Execution)
**Goal**: Execute and manage trades with surgical precision.
- **Position Sizing** (`src/risk/position_sizer.py`):
  - Calculates exact Lot Sizes (Forex) or Contract Units (Crypto).
  - **Auto-Normalization**: Handles `Volume Step` (e.g., 0.01 vs 1.0) and `Contract Size` (100k vs 1) automatically.
  - Enforces **Minimum 2.0 Risk:Reward**.
- **Trade Manager** (`src/strategy/trade_manager.py`):
  - **Lifecycle**:
    - **1.5R**: Move Stop Loss to Break-Even + 0.25R.
    - **2.0R**: Close 30% of position (Partial Profit).
    - **>2.0R**: **Trailing Stop** kicks in, trailing behind the High/Low of the last 3 closed candles.

### 🗣 The Mouth (Communication)
**Goal**: Communicate status and signals clearly.
- **Channels**:
  - **Control Room**: Your main bot chat for logs and commands.
  - **Signal Channel**: Dedicated channel for 💎 **A+ Setup** Alerts (Entry, SL, TP, RR).
- **Commands**:
  - `/status`: Check System Heartbeat.
  - `/chart [SYMBOL]`: Request a visual analysis chart.
  - `/panic`: **KILL SWITCH**. Closes all positions immediately.
  - `/maxloss [AMOUNT]`: Set a session loss limit on the fly.

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.10+** (Recommended)
- **MetaTrader 5 Terminal** (Installed and Logged In)
- **Bybit Account** (API Key with Unified Trading)

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/ekbottlebeer-genesis/Ekbottlebeer_Crypto_Forex.git
cd Ekbottlebeer_Crypto_Forex

# Create Virtual Environment
python -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate   # Windows

# Install Dependencies
pip install -r requirements.txt
```

### 3. Configuration (.env)
Create a `.env` file (see `.env.example` if available, or use the template below):
```ini
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
TELEGRAM_SIGNAL_CHANNEL_ID=your_signal_channel_id

MT5_LOGIN=123456
MT5_PASSWORD=pass
MT5_SERVER=Pepperstone-Demo

BYBIT_API_KEY=key
BYBIT_API_SECRET=secret
BYBIT_TESTNET=True
```

### 4. Running the Bot
```bash
python main.py
```
*The bot will initialize, connect to bridges, and start the "Eye" scan loop.*

---

## 🛠 Operational Guide

### Going Live (Real Money)
See [GO_LIVE_README.md](./GO_LIVE_README.md) for the specific protocol.

### Troubleshooting
- **Logs**: Check the console output or `bot.log` (if enabled in future).
- **No Trades?**:
  - Check **Time**: Are you in a lively session (London/NY)?
  - Check **News**: Is a Red Folder event active?
  - Check **RR**: Many setups are skipped if the Risk:Reward is < 2.0.

---

> "We are building a robust trading system that actually generates money with a proper visibility of the market."

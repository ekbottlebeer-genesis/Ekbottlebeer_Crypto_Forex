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
  1.  **HTF Sweep Filter**: Detects liquidity sweeps on the 1H timeframe. **Smartly identifies Double Tops/Bottoms** (EQH/EQL) for A+ confirmation.
  2.  **LTF MSS**: Waits for a Market Structure Shift on the 5m timeframe (must occur within 4 hours).
  3.  **RSI Confluence** (NEW):
      - **Longs**: RSI must be > 40 (Momentum) and < 70 (Not Overbought).
      - **Shorts**: RSI must be < 60 (Momentum) and > 30 (Not Oversold).
  4.  **FVG Entry**: Hunts for Fair Value Gaps in **Discount** (for Longs) or **Premium** (for Shorts).
  5.  **Spread Filter**: Automatically skips setups if spread > 5.0 (Protection against volatility).
- **Risk Guardrails** (`src/risk/guardrails.py`):
  - **30/30 News Rule**: Avoids trading 30 mins before/after Red Folder events (USD).
  - **Session Lock**: Pauses trading if Max Session Loss is hit.

## 🔄 Dual-Mode Operation

The bot is designed to operate in two distinct modes:

### 1. LIVE Mode (`main.py`)
- **Connects to**: Real Markets via MT5 (Forex/Gold) and Bybit (Crypto).
- **Execution**: Takes real trades with real money/demo funds.
- **Monitoring**: Scans for setups in real-time `While True` loop.

### 2. BACKTEST Mode (`backtest_module.py`)
- **Connects to**: Historical CSV Data (e.g., `XAUUSD.a_M1.csv`).
- **Execution**: Simulates trades with a Virtual Broker (0 Commission, 0.10 Slippage).
- **Monitoring**: Iterates through history bar-by-bar to validate strategy performance.

> **Note**: Both modes use the **exact same** logic (`smc_logic.py`) to ensure what you test is what you trade.

### ✋ The Hand (Execution)
**Goal**: Execute and manage trades with surgical precision.
- **Position Sizing** (`src/risk/position_sizer.py`):
  - Calculates exact Lot Sizes (Forex) or Contract Units (Crypto).
  - **Half-Risk Rescue**: If an order is rejected (Margin/Leverage), the bot **instantly retries at 50% risk**.
  - Enforces **Minimum 2.0 Risk:Reward**.
- **Trade Manager** (`src/strategy/trade_manager.py`):
  - **Smart Structural Exit**: Scans 5m structure every 5s. If a candle strictly closes against the trend structure, **exits immediately** (Market Close) to save capital.
  - **Safety Retry**: If a modification fails (latency), retries 3x before alerting.
  - **Lifecycle**:
    - **1.5R**: Move Stop Loss to Break-Even + 0.25R.
    - **2.0R**: Close 30% of position (Partial Profit).
    - **>2.0R**: **Trailing Stop** kicks in, following market structure.

### 🗣 The Mouth (Communication)
**Goal**: Communicate status and signals clearly.
- **Channels**:
  - **Control Room**: Your main bot chat for logs and commands.
  - **Signal Channel**: Dedicated channel for 💎 **A+ Setup** Alerts.
  - **Auto-Evidence**: Automatically sends a high-res chart screenshot (Entry/SL/TP/Context) for *every* trade execution.
- **Commands** (Now available in Telegram Menu):

| **Category** | **Command** | **Action** |
| --- | --- | --- |
| **Operational** | `/scan` | **Market Pulse**: View trend bias and RSI state for all watched assets. |
|  | `/status` | **Wallet**: Real-time Equity, Margin, and Free Margin. |
|  | `/check` | **Diagnostics**: Verify MT5/Broker connection and server heartbeat. |
|  | `/logs` | **Live View**: Shows last 10 lines of console output ("Are you Scanning?"). |
|  | `/chart [SYM]` | **Visual Check**: Bot sends a screenshot of the chart with HTF/LTF levels marked. |
| **Trade Mgmt** | `/positions` | **Live Trades**: View PnL, Entry, SL, and TP of all open positions. |
|  | `/history` | **Log**: View the last 5 closed trades with profit/loss. |
|  | `/close [SYM]` | **Force Exit**: Immediately close all trades for a specific symbol. |
|  | `/panic` | **KILL SWITCH**: Closes ALL open positions and cancels all pending orders. (Req: `YES_Sure`) |
| **Strategy Control** | `/pause` | **Suspend**: Stop looking for new entries (manages existing trades only). |
|  | `/resume` | **Resume**: Re-enable entry-hunting logic. |
|  | `/trail [ON/OFF]` | **Trailing Toggle**: Enable/Disable the dynamic trailing stop logic. |
| **Risk & Setup** | `/risk [0.5/1.0]` | **Adjust Risk**: Change % risk per trade on the fly. |
|  | `/maxloss [AMT]` | **Hard Stop**: Set/View the daily $ drawdown limit before auto-shutdown. |
|  | `/news` | **Calendar**: List upcoming "Red Folder" news events for the day. |
| **Testing** | `/test [SYM]` | **Force Entry**: Open a trade immediately based on CURRENT detected bias. |
|  | `/canceltest` | **Close Test**: Immediately close the last trade opened via `/test`. |
|  | `/strategy` | **Cheat Sheet**: Displays the "A+ Operator" rules in the chat. |

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

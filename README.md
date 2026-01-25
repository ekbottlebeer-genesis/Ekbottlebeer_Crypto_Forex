# 🦅 The Ekbottlebeer A+ Operator
**"The Eye, The Brain, The Hand, The Mouth"**

> **Current Status**: 🟢 LIVE / DEMO READY
> **Version**: 1.3.0 (Robustness Update)

## 🏗 System Architecture

The bot is designed as a **Money Printing Machine**, utilizing a modular "organism" architecture for absolute robustness, fault tolerance, and execution speed.

### 👁 The Eye (Monitoring)
**Goal**: See the market with absolute clarity.
- **Unified Bridge System**: 
  - **MT5 Bridge**: Connects to Forex/Gold/Indices. Features **Aggressive Symbol Discovery** (auto-detects `XAUUSD` vs `GOLD` vs `XAUUSD.a`) and **Stops Level Enforcement** to prevent Error 10013.
  - **Bybit Bridge**: Connects to Crypto Perps. Features **Split-Tunneling** for true "Demo Trading" (`api-demo.bybit.com`) vs Live/Testnet.
- **Context Awareness**: Fetches **50-Candle** HTF (1H) context for sweeps and **200-Candle** LTF (5m) structure for entries.

### 🧠 The Brain (Logic)
**Goal**: Process data and make high-probability decisions.
- **Refined SMC Strategy** (`smc_logic.py`):
  1.  **Strict HTF Sweep Filter**:
      - **Body Close Rule**: Candle body MUST close back inside the level.
      - **Wick Proportion Filter**: Wick must be >= 30% of total length.
      - **3-Candle Reclaim**: Price must trade back inside within 3 candles.
  2.  **LTF MSS**: Waits for a Market Structure Shift on the 5m timeframe (must occur within 4 hours).
  3.  **RSI Confluence**:
      - **Longs**: RSI > 40 (Momentum) and < 70 (No Overbought).
      - **Shorts**: RSI < 60 (Momentum) and > 30 (No Oversold).
  4.  **Femto-Second Decisioning**: Checks FVG entries and Risk:Reward ratios in milliseconds.

### ✋ The Hand (Execution)
**Goal**: Execute and manage trades with surgical precision.
- **Dynamic Risk Engine**: 
  - **Position Sizer**: Calculates exact lots/contracts based on your `% Risk` setting.
  - **Margin Rescue**: If an order is rejected for "Not Enough Money", the bot automatically retries specifically with **Half Risk** to capture the move.
  - **Smart Normalization**: Auto-rounds prices and volumes to broker-specific `tick_size` and `volume_step`, preventing 99% of "Invalid Request" errors.
- **Trade Manager**:
    - **1.5R**: Auto-Move SL to Break-Even + Buffer.
    - **2.0R**: Take Partial Profit (30%).
    - **Trailing Stop**: Enhanced trailing based on valid 5m Market Structure.

### 🗣 The Mouth (Communication)
**Goal**: Near-instant feedback and rich visual reporting.
- **High-Frequency Polling**: Telegram responses are decoupled for **< 1s** latency.
- **Proactive Alerting**: The bot screams (User Alert) if any critical bridge error occurs (e.g., disconnection, symbol change).
- **Auto-Evidence**: Generates a professional Chart Snippet for every trade taken, marking Entry, SL, and TP.

## 🔭 Telegram Dashboard Commands

| **Command** | **Action** |
| --- | --- |
| `/scan` | **Master Dashboard**: View Trend Bias, RSI, checklist progress, and exact levels the bot is hunting. |
| `/status` | **Wallet & Health**: Check Real-time Equity (Demo/Live), connection stats, and bridge latency. |
| `/strategy` | **Rules Cheat Sheet**: Displays the exact A+ Operator logic. |
| `/risk [val]` | **Adjust Risk**: Set % per trade (e.g., `/risk 1.0`). |
| `/trail [on/off]`| **Trail Toggle**: Enable/Disable Trailing Stop logic. |
| `/maxloss [val]` | **Drawdown Guard**: Set daily $ loss limit before auto-shutdown. |
| `/news` | **Calendar**: View localized high-impact news (Melbourne Time). |
| `/test [SYM]` | **Force Entry**: Open a micro test trade to verify connection (Remembers Ticket ID). |
| `/canceltest` | **Close Test**: Closes the specific test trade opened by the bot. |
| `/testsignalmessage` | **Broadcast Check**: Sends a test message to the Signal Channel. |
| `/chart [SYM]` | **Visualizer**: Request a live chart snapshot of any symbol. |

## 🚀 Getting Started

1.  **Python 3.10+** and **MetaTrader 5** (logged in) required.
2.  **Configuration**: 
    - Set `BYBIT_DEMO=True` in `.env` to use the official Bybit Demo environment.
    - Ensure MT5 API access is enabled in `Tools -> Options -> Expert Advisors`.
3.  **Run**: 
    - Activate venv: `source .venv/bin/activate` (Mac/Linux) or `.venv\Scripts\activate` (Win)
    - Install deps: `pip install -r requirements.txt` (Ensure `mplfinance` is included)
    - Start: `python main.py` or use the `watchdog.bat` for self-healing loops.

---

> "We are building a robust trading system that actually generates money with absolute visibility."

# 🦅 The Ekbottlebeer A+ Operator
**"The Eye, The Brain, The Hand, The Mouth"**

> **Current Status**: 🟢 LIVE / DEMO READY
> **Version**: 1.2.0 (High Precision Release)

## 🏗 System Architecture

The bot is designed as a modular organism, adhering to the "Eye, Brain, Hand, Mouth" philosophy for robustness and clarity.

### 👁 The Eye (Monitoring)
**Goal**: See the market with absolute clarity.
- **Bridges**: 
  - `src/bridges/mt5_bridge.py`: Connects to **MT5** for Forex/Gold. Supports self-healing symbol selection and suffix handling (e.g., `.a`).
  - `src/bridges/bybit_bridge.py`: Connects to **Bybit Unified Trading**. Supports both LIVE and DEMO Trading environments.
- **Data**: Fetches **50-Candle** HTF (1H) context and **200-Candle** LTF (5m) structure.

### 🧠 The Brain (Logic)
**Goal**: Process data and make high-probability decisions.
- **Refined Strategy** (`smc_logic.py`):
  1.  **Strict HTF Sweep Filter**:
      - **Body Close Rule**: Candle body MUST close back inside the level.
      - **Wick Proportion Filter**: Wick beyond the level must be >= 30% of total candle length.
      - **3-Candle Reclaim**: Price must trade back inside within 3 candles.
      - **Extreme Protection**: setup is immediately KILLED if price breaks the High/Low of the sweep candle before MSS.
  2.  **LTF MSS**: Waits for a Market Structure Shift on the 5m timeframe (must occur within 4 hours).
  3.  **RSI Confluence**:
      - **Longs**: RSI > 40 (Momentum) and < 70 (No Overbought).
      - **Shorts**: RSI < 60 (Momentum) and > 30 (No Oversold).
  4.  **FVG Entry**: Hunts for Fair Value Gaps in **Discount** (Longs) or **Premium** (Shorts).
  5.  **Spread Protection**: Automatically skips if spread > 5.0 (Protection against volatility).

### ✋ The Hand (Execution)
**Goal**: Execute and manage trades with surgical precision.
- **Dynamic Risk** (`position_sizer.py`): Calculates exact lots/units based on % risk. **Instant Half-Risk retry** on margin rejection.
- **Trade Manager** (`trade_manager.py`):
    - **1.5R**: Move to Break-Even + 0.25R.
    - **2.0R**: Partial Profit (30% close).
    - **Trailing Stop**: Enhanced trailing based on 5m market structure.

### 🗣 The Mouth (Communication)
**Goal**: Near-instant feedback and rich visual reporting.
- **High-Frequency Polling**: Telegram replies are now decoupled from the scan loop for **< 1s response time**.
- **Melbourne Localization**: All news events are localized to **Australia/Melbourne** time.

## 🔭 Telegram Dashboard Commands

| **Command** | **Action** |
| --- | --- |
| `/scan` | **Master Dashboard**: View Trend Bias, RSI, Checklist Progress, and "Waiting On" status for all assets. |
| `/status` | **Wallet**: Real-time Equity (Demo/Live), Bridge Status, and Heartbeat. |
| `/strategy` | **Rules Cheat Sheet**: Displays the word-for-word A+ Operator rules. |
| `/risk [val]` | **Adjust Risk**: Set % per trade (e.g., `/risk 1.0`). No args shows current. |
| `/trail [on/off]`| **Trail Toggle**: Enable/Disable Trailing Stop logic. Also supports `/trial`. |
| `/maxloss [val]` | **Drawdown Guard**: Set daily $ loss limit before auto-shutdown. |
| `/news` | **Calendar**: View localized high-impact news (Melbourne Time). |
| `/test [SYM]` | **Force Entry**: Open a micro test trade to verify connection. |

## 🚀 Getting Started

1.  **Python 3.10+** and **MetaTrader 5** (logged in) required.
2.  **Configuration**: Set `BYBIT_DEMO=True` in `.env` to trade with your $500 Demo USDT.
3.  **Run**: Execute `python main.py` or use the `watchdog.bat` for self-healing loops.

---

> "We are building a robust trading system that actually generates money with absolute visibility."

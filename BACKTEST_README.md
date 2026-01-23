# 🧪 Backtest Mode: The Time Machine

The **Ekbottlebeer Backtester** allows you to validate the "A+ Operator" strategy using historical data before risking real capital. It simulates the bot's "Eye" and "Brain" with high precision (bar-by-bar wick checking).

## ⚡ Features
- **Bar-by-Bar Precision**: Checks SL/TP hits on M1 wicks inside the 5m candle.
- **Silent Mode**: Redirects all Telegram alerts to `backtest_events.log`.
- **Visual Auditing**: Generates a chart screenshot for EVERY trade taken (`backtest_trade_X.png`).
- **Simulated Broker**: Tracks Equity, Slippage (0.5 pips), and Commissions.

---

## 🛠 Prerequisites

### 1. Data Source (CSV)
You need 1-Minute (M1) OHLCV data. The headers **must** include:
`Time, Open, High, Low, Close, Volume`

#### How to get data?
**Option A: MetaTrader 5 (Easiest)**
1. Open MT5 -> Tools -> History Center (`F2`).
2. Select Symbol (e.g., `EURUSD`).
3. Select `1 Minute (M1)`.
4. Click **Export** -> Save as CSV (e.g., `EURUSD_M1.csv`).

**Option B: Bybit**
1. Download historical data from Bybit Data usage.
2. Convert to standard CSV format.

### 2. File Placement
Place your `.csv` file in the project root folder.

---

## 🚀 How to Run

1. Open `backtest_module.py`.
2. Scroll to the bottom (`if __name__ == "__main__":`).
3. Update the filename to match your CSV:
   ```python
   engine = BacktestEngine("EURUSD_M1.csv", "EURUSD")
   ```
4. Run the module:
   ```bash
   python backtest_module.py
   ```

---

## 📊 Output & Reporting

After the run completes, check the generated artifacts:

1. **`backtest_results.csv`**: A row-by-row log of every trade (Entry, Exit, PnL, Duration).
2. **`backtest_events.log`**: A text log of all "Telegram" messages (Signals, SL updates, TP hits).
3. **`debug_charts/`**: A folder containing screenshots of every trade setup.
   - *Review these images to verify if the bot is "seeing" what you see.*

### Performance Metrics
The summary printed at the end includes:
- **Win Rate**: Target > 40% (if R:R is 1:2).
- **Profit Factor**: Gross Win / Gross Loss. Target > 1.5.
- **Net PnL**: Total hypothetical profit.

---

## ⚠️ Limitations
- **Spread Simulation**: Currently assumes a fixed `0.5 pip` slippage. It does *not* simulate variable spreads during news (unless your CSV has Bid/Ask data, which is rare).
- **Execution Latency**: Assumes instant execution.
- **Liquidity**: Assumes full fills (no volume limit).

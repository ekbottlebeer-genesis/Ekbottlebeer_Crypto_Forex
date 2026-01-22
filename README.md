# The Ekbottlebeer A+ Operator
**Version:** 1.0 (Strategic Final)
**System Constitution**

This repository contains the "Brain" of the automated SMC trading system. It is designed to run on a dedicated Windows node with a "Self-Healing" watchdog.

---

## 1. Operational Manual (The Strategy)

### The Setup (A+ SMC)
1.  **Anchor (Search)**: The bot scans 1H/4H charts for **Liquidity Sweeps** of PDH/PDL or EQH/EQL.
2.  **Trigger (Confirm)**: Once a sweep is found, it drops to **5m** to look for a **Market Structure Shift (MSS)** with a body close.
3.  **Entry (Execute)**: If MSS is confirmed, a Limit Order is placed at the **Fair Value Gap (FVG)**.
4.  **Validation**:
    *   **SL**: Prominent Swing (3-candle pivot) of the sweep.
    *   **TP**: Opposite external liquidity (Min 2.0 RR).

### Strategic Sessions (UTC Independent)
*   **Asia Core (00:00 - 08:00)**: JPY, AUD, NZD, XAU.
*   **London Lead (07:00 - 15:00)**: GBP, EUR, DAX, XAU.
*   **NY Power (13:00 - 20:00)**: USD, NASDAQ, XAU.
*   **Crypto Background**: 24/7 Monitoring (BTC, ETH, SOL, etc.).

---

## 2. The Communication Map (Telegram Command Center)

Your Telegram Chat is the "Cockpit".

### Operational
*   `/scan` - **Market Pulse**: View trend bias and watchlist status.
*   `/status` - **Wallet**: View Equity/Margin.
*   `/check` - **Diagnostics**: Test Broker connections.
*   `/logs` - **Live View**: Last 10 lines of console output.
*   `/chart [SYM]` - **Visual Audit**: Request annotated chart screenshot.

### Trade Management
*   `/positions` - **Live Trades**: View open PnL/SL/TP.
*   `/history` - **Log**: Last 5 closed trades.
*   `/close [SYM]` - **Force Exit**: Close trades for a symbol.
*   `/panic` - **KILL SWITCH**: Closes ALL positions. **Requires `YES_Sure` confirmation.**

### Strategy Control
*   `/pause` - **Suspend**: Stop looking for new entries.
*   `/resume` - **Resume**: Re-enable scanning.
*   `/trail [ON/OFF]` - **Trailing**: Toggle dynamic trailing stop.

### Risk & Setup
*   `/risk [VAL]` - **Adjust Risk**: Set % risk per trade (e.g., `/risk 0.5`).
*   `/maxloss [AMT]` - **Hard Stop**: Set Session Loss Limit.
*   `/news` - **Calendar**: upcoming "Red Folder" events.

### Testing
*   `/test [SYM]` - **Force Entry**: Open trade immediately on current bias.
*   `/canceltest` - **Close Test**.
*   `/strategy` - **Cheat Sheet**: Display rules.

---

## 3. The Recovery Plan (Self-Healing)

### Scenario A: Bot Crashes / Script Errors
*   **Action**: Do nothing.
*   **Result**: The `watchdog.bat` script will detect the process exit, wait 5 seconds, and auto-restart.

### Scenario B: Adding New Features / Fixing Bugs
1.  **Develop**: Make changes on your Mac (Building Node).
2.  **Push**: Run `./gpush.sh "Commit Message"` in terminal.
3.  **Deploy**: The Windows Watchdog will automatically `git pull` the changes on its next cycle or restart.

### Scenario C: "Panic" Button Used
1.  **Action**: You sent `/panic` then `YES_Sure`.
2.  **Result**: All trades closed. Bot logic suspended.
3.  **Recovery**: To restart trading, send `/resume`.

---

## 4. Installation & Setup

1.  **Clone Repository**: `git clone <repo_url>`
2.  **Create Venv**: `python -m venv .env`
3.  **Configure `.env`**: Fill in Telegram Token, Chat ID, and Broker Keys.
4.  **Launch**: Double-click `watchdog.bat`.

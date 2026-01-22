# 🚀 GO LIVE: Ekbottlebeer A+ Operator

This document outlines the critical steps to transition the bot from **DEMO/PAPER** mode to **LIVE** money trading.

> [!CAUTION]
> **READ CAREFULLY.** Automated trading involves significant risk. Ensure the bot has been profitable in Demo for at least 2 weeks before enabling Live execution.

---

## 1. Environment Variables (`.env`)

You must update your credentials in the `.env` file.

### For Bybit (Crypto)
1.  **Log in to Bybit Main Site**.
2.  Go to **API Management**.
3.  Create a new Key with **Read-Write** permissions and **Unified Trading** enabled.
4.  Update `.env`:
    ```ini
    BYBIT_API_KEY=your_live_key
    BYBIT_API_SECRET=your_live_secret
    BYBIT_TESTNET=False  <-- CHANGE THIS TO FALSE
    ```

### For Pepperstone (MT5)
1.  **Open MT5 Terminal**.
2.  File -> **Login to Trade Account**.
3.  Enter your **LIVE** Login ID, Password, and select the **Live Server** (e.g., `Pepperstone-Live`).
4.  Update `.env`:
    ```ini
    MT5_LOGIN=your_live_login_id
    MT5_PASSWORD=your_live_password
    MT5_SERVER=Pepperstone-Live
    ```

---

## 2. Configuration & Risk

Check `src/risk/position_sizer.py` and `main.py` parameters.

-   **Risk Percentage**: Ensure `default_risk_pct` is safe (start with `0.5` or `1.0`%).
-   **Max Session Loss**: Use the `/maxloss` command immediately after startup to set a hard stop (e.g., `/maxloss 500`).
-   **Lot Sizes**: Verify that the `PositionSizer` logic aligns with your account size and contract specifications (Standard vs Micro lots).

---

## 3. Operational Checklist

-   [ ] **VPS/Server**: Ensure the bot is running on a stable VPS (e.g., AWS EC2, Contabo) in the same region as the broker servers for low latency.
-   [ ] **Watchdog**: Ensure `watchdog.bat` is running to auto-restart the bot if it crashes.
-   [ ] **Telegram**: Verify you are receiving "Heartbeat" messages every hour.
-   [ ] **Time Sync**: Ensure the server time is strictly synced (NTP).

---

## 4. Emergency Procedures

### The KILL SWITCH
If the bot behaves unexpectedly, **IMMEDIATELY** send the following command in Telegram:

`/panic`

Then confirm with:

`YES_Sure`

This will attempt to **CLOSE ALL POSITIONS** and **STOP** the bot loop.

### Manual Override
If the bot fails to close:
1.  **MT5**: Open the terminal and click "Close All" or manually close trades.
2.  **Bybit**: Open the app and hit "Close All".

---

## 5. Verification Mode
Before leaving the bot unattended:
1.  Run it in **Forward Test** mode (Visualizer only) for 1 session.
2.  Check the charts sent via `/chart` to ensure logic aligns with your strategy.

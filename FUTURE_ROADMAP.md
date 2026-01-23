# 🚀 Future Features & Roadmap

This document tracks planned enhancements to evolve the Ekbottlebeer Scalper Bot into a **Professional Hedge-Fund Grade System**.

## 1. Core Infrastructure (Stability & Speed) "Money Printing Foundation"
- [ ] **AsyncIO Migration (High Priority)**
    - *Goal*: Move from synchronous `time.sleep()` loops to proper `asyncio`.
    - *Benefit*: The bot will handle Telegram commands *instantly* while scanning 20+ pairs, without "freezing" during network requests.
    
- [ ] **Database Integration (SQLite)**
    - *Goal*: Replace `state.json` with a robust SQL database (`trade_history.db`).
    - *Benefit*: 
        - **Persistent Auditing**: Every trade, every error, every PnL change is recorded forever.
        - **Advanced Analytics**: Generate Win/Loss, Drawdown, and Equity Curve reports on demand.
        - **Crash Resilience**: Zero data loss even if the server power cuts.

- [ ] **Process Guard (Watchdog)**
    - *Goal*: Ensure the bot is **Immortal**.
    - *Benefit*: If the bot crashes (e.g. Memory Error), a separate Supervisor script automatically restarts it within 5 seconds and notifies you on Telegram.

## 2. Risk & Strategy Logic
- [ ] **Full News Protection (Crypto/Bybit)**
    - *Goal*: Extend the "move-to-breakeven" logic to Bybit Perpetual positions before high-impact USD news.
    - *Currently*: Only active for MT5 Forex.

- [ ] **Smart Spread Filter**
    - *Goal*: Dynamic spread protection.
    - *Logic*: Scan historic spread averages and only trade when spread is normal. Reject trade if spread spikes > 2x average (common during liquidity crunches).

## 3. Advanced Usability
- [ ] **Web Dashboard (Streamlit/Next.js)**
    - *Goal*: A visual "Command Center" running on localhost.
    - *Features*: Real-time chart of Equity vs Balance, active position table, and one-click "Panic" buttons.

- [ ] **Smarter `/canceltest`**
    - *Goal*: Instantly undo specific test trades to prevent accidental losses during validation.

---

> **Design Philosophy**: 
> 1. Protection First (Capital Preservation)
> 2. Execution Speed (Get the Price)
> 3. Transparency (Know Why)

# src/utils/state_manager.py
import json
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class StateManager:
    def __init__(self, filepath="state.json"):
        self.filepath = filepath
        self.state = self.load_state()

    def load_state(self):
        """Loads state from JSON file or initializes default."""
        
        # Default State Definition
        default_state = {
            "system_status": "active",
            "crypto_status": "active",
            "forex_status": "active",
            "last_heartbeat": None,
            "session_pnl": 0.0,
            "last_pnl_date": datetime.now().strftime("%Y-%m-%d"), 
            "current_session": "waiting",
            "active_sweeps": {}, 
            "active_trades": [], 
            "pending_setups": [], 
            "last_scan_data": {}, 
            "watchlists": {
                "ASIA": ["USDJPY", "AUDUSD"],
                "LONDON": ["GBPUSD", "EURUSD", "XAUUSD"],
                "NY": ["XAUUSD", "US30", "NAS100"]
            },
            "trade_history": [] 
        }

        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    state = json.load(f)
                    
                    # MERGE DEFAULTS: Ensure all keys exist
                    for key, value in default_state.items():
                        if key not in state:
                            state[key] = value
                    
                    # DATE CHECK: Reset PnL if new day
                    current_date = datetime.now().strftime("%Y-%m-%d")
                    saved_date = state.get('last_pnl_date', "1970-01-01")
                    if saved_date != current_date:
                        logger.info(f"🔄 NEW DAY DETECTED: Resetting Session PnL (Was: {state.get('session_pnl', 0)})")
                        state['session_pnl'] = 0.0
                        state['last_pnl_date'] = current_date
                        # Auto-unpause if paused due to loss?
                        if state.get('system_status') == 'paused':
                             logger.info("🔄 Auto-Resuming System for New Day.")
                             state['system_status'] = 'active'
                             
                    return state
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
        
        return default_state

    def save_state(self):
        """Persists current state to JSON."""
        try:
            with open(self.filepath, "w") as f:
                json.dump(self.state, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def update_scan_data(self, symbol, data):
        """Updates the dashboard status for a symbol."""
        if 'last_scan_data' not in self.state:
            self.state['last_scan_data'] = {}
        self.state['last_scan_data'][symbol] = data
        self.save_state()

    def update_sweep(self, symbol, sweep_data):
        """Updates detected HTF sweep for a symbol."""
        self.state['active_sweeps'][symbol] = sweep_data
        self.save_state()

    def clear_sweep(self, symbol):
        if symbol in self.state['active_sweeps']:
            del self.state['active_sweeps'][symbol]
            self.save_state()

    def add_trade(self, trade_data):
        self.state['active_trades'].append(trade_data)
        self.save_state()

    def remove_trade(self, ticket):
        self.state['active_trades'] = [t for t in self.state['active_trades'] if t.get('ticket') != ticket]
        self.save_state()

    def add_pending_setup(self, setup_data):
        # Remove existing for same symbol to avoid dupes/stale
        self.remove_pending_setup(setup_data['symbol'])
        self.state['pending_setups'].append(setup_data)
        self.save_state()

    def remove_pending_setup(self, symbol):
        self.state['pending_setups'] = [s for s in self.state['pending_setups'] if s.get('symbol') != symbol]
        self.save_state()

    def updates_session_pnl(self, amount):
        self.state['session_pnl'] = self.state.get('session_pnl', 0.0) + amount
        self.save_state()

    def log_closed_trade(self, trade_data):
        """Logs a closed trade to history (Highlander rule: Keep only last 10)."""
        history = self.state.get('trade_history', [])
        history.insert(0, trade_data) # Prepend to show newest first
        self.state['trade_history'] = history[:10] # Keep last 10
        self.save_state()

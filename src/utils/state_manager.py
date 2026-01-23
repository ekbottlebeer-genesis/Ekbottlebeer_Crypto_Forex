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
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
        
        # Default State
        return {
            "system_status": "active",
            "crypto_status": "active",
            "forex_status": "active",
            "last_heartbeat": None,
            "session_pnl": 0.0,
            "current_session": "waiting",
            "active_sweeps": {}, # {symbol: {level: 1.23, side: 'buy', timestamp: ...}}
            "active_trades": [], # {symbol: {ticket: 123, entry: ..., sl: ..., tp: ...}}
            "watchlists": {
                "ASIA": ["USDJPY", "AUDUSD"],
                "LONDON": ["GBPUSD", "EURUSD", "XAUUSD"],
                "NY": ["XAUUSD", "US30", "NAS100"]
            }
        }

    def save_state(self):
        """Persists current state to JSON."""
        try:
            with open(self.filepath, "w") as f:
                json.dump(self.state, f, indent=4)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

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

    def updates_session_pnl(self, amount):
        self.state['session_pnl'] = self.state.get('session_pnl', 0.0) + amount
        self.save_state()

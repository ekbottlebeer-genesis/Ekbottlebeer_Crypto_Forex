# src/strategy/session_manager.py
import logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self):
        self.crypto_symbols = [
            "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", 
            "XRPUSDT", "ADAUSDT", "XAUTUSDT"
        ]
        
        # Define Sessions (UTC Times) with Specific Watchlists
        self.sessions = {
            "Asia": {
                "start": 22, "end": 8, # Sydney Opens 22:00 UTC
                "symbols": ["USDJPY", "AUDUSD", "NZDUSD", "XAUUSD", "EURUSD"],
            },
            "London": {
                "start": 8, "end": 16,
                "symbols": ["EURUSD", "GBPUSD", "XAUUSD"],
            },
            "NewYork": {
                "start": 13, "end": 22,
                "symbols": ["XAUUSD", "US30", "NAS100", "USDJPY", "EURUSD"],
            }
        }

    def get_current_session_info(self):
        """
        Returns active session names and the combined watchlist.
        """
        current_utc = datetime.now(pytz.utc)
        current_hour = current_utc.hour
        
        active_sessions = []
        active_symbols = set()
        
        # Add Crypto by default (Overlay)
        # Note: Volatility filter logic should be applied at strategy level before execution
        for sym in self.crypto_symbols:
            active_symbols.add(sym)
            
        # Check Forex Sessions
        for name, config in self.sessions.items():
            start = config["start"]
            end = config["end"]
            
            is_active = False
            if start < end:
                # Normal Day Session (e.g. 08 to 16)
                if start <= current_hour < end:
                    is_active = True
            else:
                # Overnight Session (e.g. 22 to 08)
                if current_hour >= start or current_hour < end:
                    is_active = True
            
            if is_active:
                active_sessions.append(name)
                for sym in config["symbols"]:
                    active_symbols.add(sym)
                    
        return {
            "sessions": active_sessions,
            "watchlist": list(active_symbols),
            "utc_hour": current_hour
        }

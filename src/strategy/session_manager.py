# src/strategy/session_manager.py
import logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self):
        # Define Sessions (UTC)
        # Asia: 00:00 - 08:00
        # London: 07:00 - 15:00
        # NY: 13:00 - 20:00
        self.sessions = {
            "ASIA": {"start": 0, "end": 8, "symbols": ["USDJPY.a", "AUDUSD.a", "NZDUSD.a", "XAUUSD.a"]},
            "LONDON": {"start": 7, "end": 15, "symbols": ["GBPUSD.a", "EURUSD.a", "DAX.a", "XAUUSD.a", "XAUUSDT.a"]},
            "NY": {"start": 13, "end": 20, "symbols": ["XAUUSD.a", "XAUUSDT.a", "US30.a", "NAS100.a", "USDJPY.a"]}
        }
        
        # Crypto is 24/7
        self.crypto_symbols = [
            "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", 
            "XRPUSDT", "ADAUSDT", "XAUTUSDT"
        ]

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
            
            # Simple check for same-day windows
            # If 00:00 to 08:00, straight forward checking
            if start <= current_hour < end:
                active_sessions.append(name)
                for sym in config["symbols"]:
                    active_symbols.add(sym)
                    
        return {
            "sessions": active_sessions,
            "watchlist": list(active_symbols),
            "utc_hour": current_hour
        }

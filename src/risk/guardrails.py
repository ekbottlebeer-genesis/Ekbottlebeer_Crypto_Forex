# src/risk/guardrails.py
import logging
from datetime import datetime
import requests
import pandas as pd

logger = logging.getLogger(__name__)

class RiskGuardrails:
    def __init__(self, state_manager):
        self.state_manager = state_manager
        self.max_session_loss = 100.0 # Default, should be loaded from config/state
        self.news_api_key = "YOUR_NEWS_API_KEY" # Placeholder
        self.high_impact_events = []

    def check_session_loss(self):
        """
        Checks if the current session PnL has exceeded the max allowed loss.
        Returns True if trading should be HALTED.
        """
        current_loss = self.state_manager.state.get('session_pnl', 0.0)
        # Assuming loss is represented as negative number, so if current_loss < -max_loss
        if current_loss <= -self.max_session_loss:
            logger.warning(f"Session Loss Limit Hit: {current_loss} <= -{self.max_session_loss}")
            return True
        return False

    def check_spread(self, symbol, current_spread, max_spread_pips):
        """
        Returns True if spread is acceptable (below threshold).
        """
        if current_spread > max_spread_pips:
            logger.info(f"Spread High for {symbol}: {current_spread} > {max_spread_pips}")
            return False
        return True

    def fetch_calendar(self):
        """
        Placeholder for fetching economic calendar.
        Ideally uses an API like ForexFactory (via scraper) or similar.
        Populates self.high_impact_events
        """
        # TODO: Implement real news fetching
        self.high_impact_events = []
        pass

    def check_news(self, symbol):
        """
        Block 3.3: High-Impact News Guardrail.
        Returns True if SAFE to trade (no high impact news in +/- 30 mins).
        """
        if not self.high_impact_events:
            self.fetch_calendar() # Refresh if empty
            
        current_time = datetime.now()
        
        for event in self.high_impact_events:
            # Check currency match (e.g. USD event affects XAUUSD, EURUSD)
            # Logic: If symbol contains event['currency']...
            if event['currency'] in symbol:
                event_time = event['time']
                diff = (current_time - event_time).total_seconds() / 60.0
                
                # If within 30 mins before (-30) or 30 mins after (+30)
                if -30 <= diff <= 30:
                    logger.warning(f"News Filter: Trading Paused for {symbol} due to {event['name']} ({diff:.0f} mins)")
                    return False
                    
        return True

    def protect_active_trades(self, active_trades, bridge):
        """
        Checks if active trades need to be moved to BE due to upcoming news (T-5 mins).
        """
        current_time = datetime.now()
        for trade in active_trades:
            symbol = trade['symbol']
            
            for event in self.high_impact_events:
                 if event['currency'] in symbol:
                     event_time = event['time']
                     # Diff is negative if before event. e.g. -5 means 5 mins before.
                     diff = (current_time - event_time).total_seconds() / 60.0
                     
                     # 5 minutes before news (-5)
                     if -6 <= diff <= -4 and not trade.get('is_be', False):
                         logger.info(f"News Protection: Moving {symbol} to BE (T-5 mins to {event['name']})")
                         # Move SL to Entry
                         bridge.modify_order(trade['ticket'], sl=trade['entry_price'])
                         trade['is_be'] = True
                         self.state_manager.save_state()

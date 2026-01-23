# src/risk/guardrails.py
import logging
from datetime import datetime
import requests
import pandas as pd

logger = logging.getLogger(__name__)

class RiskGuardrails:
    def __init__(self, state_manager):
        self.state_manager = state_manager
        self.max_session_loss = 500.0 # Default
        self.high_impact_events = []
        self.last_fetch_time = datetime.min
        # Load News Mode preference (Default: ON)
        self.news_filter_enabled = self.state_manager.state.get('news_filter_enabled', True)

    def set_news_mode(self, enabled: bool):
        """Toggles the News Filter ON/OFF."""
        self.news_filter_enabled = enabled
        self.state_manager.state['news_filter_enabled'] = enabled
        self.state_manager.save_state()
        return f"News Filter set to: {'ON' if enabled else 'OFF'}"

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
        Fetches economic calendar from Forex Factory (XML feed).
        Filters for USD High Impact (Red Folder) events.
        """
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            # Simple XML parsing
            import xml.etree.ElementTree as ET
            import pytz
            root = ET.fromstring(response.content)
            
            events = []
            
            for child in root:
                try:
                    country = child.find('country').text
                    impact = child.find('impact').text
                    date_str = child.find('date').text
                    time_str = child.find('time').text
                    
                    # Filter: US Market (USD) and High Impact (Red)
                    if country != 'USD':
                        continue
                    if impact != 'High':
                        continue
                        
                    # Parse Datetime
                    # Format is usually: date: MM-DD-YYYY, time: 1:30pm
                    dt_str = f"{date_str} {time_str}"
                    event_dt = datetime.strptime(dt_str, "%m-%d-%Y %I:%M%p")
                    
                    # Convert to UTC (Assuming NY time for FF XML)
                    tz_ny = pytz.timezone('America/New_York')
                    event_dt = tz_ny.localize(event_dt).astimezone(pytz.UTC)
                    
                    events.append({
                        'title': child.find('title').text,
                        'time': event_dt,
                        'impact': impact,
                        'currency': 'USD'
                    })
                    
                except Exception as e:
                    continue
                    
            self.high_impact_events = events
            self.last_fetch_time = datetime.now()
            logger.info(f"Fetched {len(events)} High Impact USD events from Forex Factory.")
            
        except Exception as e:
            logger.error(f"Failed to fetch Forex Factory calendar: {e}")
            self.high_impact_events = []

    def check_news(self, symbol):
        """
        Checks if high-impact news is upcoming (30m buffer).
        Returns True if SAFE to trade, False if UNSAFE.
        """
        if not self.news_filter_enabled:
            return True

        # Refresh if stale (older than 4 hours) or empty
        if not self.high_impact_events or (datetime.now() - self.last_fetch_time).total_seconds() > 14400:
             self.fetch_calendar()
        
        if not self.high_impact_events:
            return True
            
        # Check against upcoming events
        # Usually need pytz for comparison
        import pytz
        now_utc = datetime.now(pytz.UTC)
        
        for event in self.high_impact_events:
             # Check if symbol relates to USD? Most pairs do.
             # Strict safety: If ANY USD Red Folder, we pause EVERYTHING.
             time_diff = (event['time'] - now_utc).total_seconds() / 60.0
             
             if -30 <= time_diff <= 30:
                 logger.warning(f"🚫 NEWS HALT: {event['title']} at {event['time']} (Diff: {time_diff:.1f}m)")
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
                         logger.info(f"News Protection: Moving {symbol} to BE (T-5 mins to {event['title']})")
                         # Move SL to Entry
                         bridge.modify_order(trade['ticket'], sl=trade['entry_price'])
                         trade['is_be'] = True
                         self.state_manager.save_state()

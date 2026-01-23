import logging
import os
import json
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
        # Load News Mode preference (Default: OFF as per user request)
        self.news_filter_enabled = self.state_manager.state.get('news_filter_enabled', False)

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
        Fetches economic calendar. Checks local cache first to avoid API limits.
        """
        import json
        import pytz
        cache_file = "news_cache.json"
        now_utc = datetime.now(pytz.UTC)
        
        # 1. Try Load from Cache
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    cache = json.load(f)
                    cache_time = datetime.fromisoformat(cache['timestamp'])
                    
                    # If cache is less than 12 hours old, use it
                    if (datetime.now() - cache_time).total_seconds() < 43200:
                         logger.info(f"Loaded {len(cache['events'])} news events from local cache ({cache['timestamp']})")
                         # Re-hydrate dates
                         self.high_impact_events = []
                         for e in cache['events']:
                             dt = datetime.fromisoformat(e['time'])
                             if dt.tzinfo is None: dt = pytz.UTC.localize(dt)
                             
                             # FILTER: Only load future events (or very recent past < 2h)
                             if (dt - now_utc).total_seconds() > -7200:
                                 self.high_impact_events.append({
                                     'title': e['title'],
                                     'time': dt,
                                     'impact': e['impact'],
                                     'currency': e['currency']
                                 })
                         
                         self.last_fetch_time = cache_time
                         return
            except Exception as e:
                logger.warning(f"Failed to load news cache: {e}")

        # 2. Fetch from API
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # XML Parsing
            import xml.etree.ElementTree as ET
            root = ET.fromstring(response.content)
            
            events = []
            cache_events = [] # For JSON serialization
            
            for child in root:
                try:
                    country = child.find('country').text
                    impact = child.find('impact').text
                    if country != 'USD' or impact != 'High': continue
                        
                    dt_str = f"{child.find('date').text} {child.find('time').text}"
                    event_dt = datetime.strptime(dt_str, "%m-%d-%Y %I:%M%p")
                    tz_ny = pytz.timezone('America/New_York')
                    event_dt = tz_ny.localize(event_dt).astimezone(pytz.UTC)
                    
                    # FILTER: Only keep future events (or very recent past)
                    if (event_dt - now_utc).total_seconds() > -7200:
                        evt = {
                            'title': child.find('title').text,
                            'time': event_dt,
                            'impact': impact,
                            'currency': 'USD'
                        }
                        events.append(evt)
                        
                        # Store serialized version
                        evt_ser = evt.copy()
                        evt_ser['time'] = evt['time'].isoformat()
                        cache_events.append(evt_ser)
                    
                except: continue
                    
            self.high_impact_events = events
            self.last_fetch_time = datetime.now()
            logger.info(f"Fetched {len(events)} Future High Impact USD events from Forex Factory.")
            
            # 3. Save to Cache
            try:
                with open(cache_file, 'w') as f:
                    # Save even if empty to track partial fetches
                    json.dump({'timestamp': datetime.now().isoformat(), 'events': cache_events}, f)
            except Exception as e:
                logger.warning(f"Failed to save news cache: {e}")
            
        except Exception as e:
            logger.error(f"Failed to fetch Forex Factory calendar: {e}")
            if "429" in str(e): logger.warning("Hypersensitive Rate Limit active. Cool down enforced.")
            self.last_fetch_time = datetime.now() # Cooldown

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

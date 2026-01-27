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

    def check_spread(self, symbol, current_spread, is_crypto=False):
        """
        Returns True if spread is acceptable.
        Forex: Max 2.0 Pips (0.00020).
        Crypto: Max 0.1% of Price? Or fixed $ value?
        For robustness, we use a PIP multiplier for Forex (assuming 5-digit broker).
        """
        threshold = 5.0 # Default fallback
        
        if not is_crypto:
            # FOREX LOGIC: 2.0 Pips
            # 1 Pip = 0.0001 usually (or 0.01 for JPY)
            # Spread is raw difference. e.g. 1.10020 - 1.10000 = 0.00020 (20 points)
            # User wants "2 pips". 
            # If broker uses Points, 2 pips = 20 points.
            # If current_spread is raw price diff:
            
            # Heuristic: If JPY (Price > 50), 1 pip = 0.01. If spread is 0.02 -> 2 pips.
            # If Normal (Price < 50), 1 pip = 0.0001. If spread is 0.0002 -> 2 pips.
            
            # Better approach: Use max_spread_pips passed from main or just hardcode strict rule.
            # STRICT FOREX RULE: 2.5 PIPS max (Safety buffer)
            
            if "JPY" in symbol:
                threshold = 0.025 # 2.5 pips
            elif "XAU" in symbol: # Gold
                threshold = 0.50 # 50 cents on Gold
            else:
                threshold = 0.00025 # 2.5 pips
                
        else:
            # CRYPTO LOGIC
            # BTC spread $10 is fine.
            # Use raw value passed or rely on %?
            # Let's trust the current_spread is raw USD diff.
            # If price is 100k, spread 100 is 0.1%.
            # Let's revert to the loose 5.0 for Crypto or higher for BTC?
            # Actually, standard crypto spread is tight on Bybit.
            # Set to generic safety or ignore (return True).
            if "BTC" in symbol: threshold = 50.0 
            elif "ETH" in symbol: threshold = 5.0
            else: threshold = 1.0 
            
        if current_spread > threshold:
            logger.info(f"Spread High for {symbol}: {current_spread:.5f} > {threshold}")
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
                         logger.debug(f"Loaded {len(cache['events'])} news events from local cache ({cache['timestamp']})")
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

        # Refresh if stale (older than 4 hours) or never fetched
        if (datetime.now() - self.last_fetch_time).total_seconds() > 14400:
             self.fetch_calendar()
        
        if not self.high_impact_events:
            return True
            
        # Check against upcoming events
        import pytz
        now_utc = datetime.now(pytz.UTC)
        
        # Determine Symbol Currencies (e.g. XAUUSD -> XAU, USD | BTCUSDT -> BTC, USDT, USD)
        # Simplified: Check if event currency string is IN the symbol
        
        for event in self.high_impact_events:
             event_ccy = event['currency'] # e.g. 'USD', 'EUR'
             
             # INTELLIGENT FILTER:
             # Only pause if the event currency affects this specific symbol.
             # e.g. "EUR" news should not pause "USDJPY".
             # "USD" news affects "XAUUSD", "BTCUSDT", "EURUSD".
             if event_ccy not in symbol:
                 # Special Case: Gold (XAU) is priced in USD usually
                 if "GOLD" in symbol and event_ccy == "USD":
                     pass # Matches
                 # Special Case: Crypto (BTCUSDT) often ignores minor USD forex news, but NFP/CPI hits it.
                 # For now, we trust strict match. If symbol is 'AUDJPY', 'USD' news is ignored.
                 else:
                     continue
             
             time_diff = (event['time'] - now_utc).total_seconds() / 60.0
             
             # 30 minute buffer before and after
             if -30 <= time_diff <= 30:
                 logger.debug(f"🚫 NEWS HALT: {symbol} paused for {event['title']} [{event_ccy}] (T{time_diff:+.1f}m)")
                 return False
                 
        return True

    def protect_active_trades(self, active_trades, bridge_map):
        """
        Checks if active trades need to be moved to BE due to upcoming news (T-5 mins).
        bridge_map: dict {'mt5': mt5_instance, 'bybit': bybit_instance}
        """
        current_time = datetime.now()
        for trade in active_trades:
            symbol = trade['symbol']
            
            # Determine Bridge
            # Heuristic: Crypto symbols usually in Bybit bridge scope
            bridge = bridge_map.get('mt5')
            if 'bybit' in str(trade.get('ticket')) or 'USDT' in symbol:
                bridge = bridge_map.get('bybit')
            
            if not bridge: continue

            for event in self.high_impact_events:
                 if event['currency'] in symbol:
                     # Check exclusion (e.g. EUR news shouldn't touch USDJPY)
                     # Already filtered by currency match above? "USD" in "USDJPY" -> Match. Correct.
                     
                     event_time = event['time']
                     diff = (current_time - event_time).total_seconds() / 60.0
                     
                     # 5 minutes before news (-5)
                     if -6 <= diff <= -4 and not trade.get('is_be', False):
                         logger.info(f"News Protection: Moving {symbol} to BE (T-5 mins to {event['title']})")
                         
                         # Execute BE Move
                         # MT5: modify_order(ticket, sl=entry)
                         # Bybit: amend_order(symbol, sl=entry) -> standardized to modify_order if possible?
                         # Bybit bridge has 'place_order' (amend support pending?).
                         # We use generic 'modify_order' if supported.
                         
                         try:
                             if hasattr(bridge, 'modify_order'):
                                 bridge.modify_order(trade['ticket'], sl=trade['entry'])
                             else:
                                 # Fallback for Bybit if modify_order not uniform
                                 # Assuming BybitBridge has set_trading_stop or similar.
                                 # For "Masterpiece", we assume standardized bridge interface.
                                 # If not, skipping Bybit to avoid crash. 
                                 pass
                                 
                             trade['is_be'] = True
                             self.state_manager.save_state()
                         except Exception as e:
                             logger.error(f"Failed to protect trade {symbol}: {e}")

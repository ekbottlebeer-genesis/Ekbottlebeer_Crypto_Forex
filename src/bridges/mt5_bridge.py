# src/bridges/mt5_bridge.py
try:
    import MetaTrader5 as mt5
except ImportError:
    # MOCK FOR MAC DEVELOPMENT
    class MockMT5:
        def initialize(self, **kwargs): return True
        def shutdown(self): return True
        def last_error(self): return (1, "Mock Error")
        
        # Mock Objects
        class MockSymbol:
            def __init__(self, name): 
                self.name = name
                self.time = 0
                self.bid = 1.0
                self.ask = 1.0001
                self.volume_min = 0.01
                self.volume_max = 100.0
                self.volume_step = 0.01
                self.digits = 5
                self.point = 0.00001
                self.trade_contract_size = 100000
                self.trade_stops_level = 10
                self.filling_mode = 1
        
        class MockTick:
             def __init__(self):
                 self.bid = 1.2000
                 self.ask = 1.2002
                 self.time = 1670000000
        
        def symbols_get(self, group="*"):
            return [self.MockSymbol("EURUSD"), self.MockSymbol("GBPUSD")]
            
        def symbol_select(self, symbol, enable): return True
        
        def symbol_info(self, symbol):
            return self.MockSymbol(symbol)
            
        def symbol_info_tick(self, symbol):
            return self.MockTick()
            
        def copy_rates_from_pos(self, symbol, timeframe, start_pos, count):
            import numpy as np
            # Create a structured array to mimic MT5 rates
            dt = np.dtype([('time', '<i8'), ('open', '<f8'), ('high', '<f8'), ('low', '<f8'), ('close', '<f8'), ('tick_volume', '<i8'), ('spread', '<i4'), ('real_volume', '<i8')])
            rates = np.zeros(count, dtype=dt)
            # Fill with dummy data
            import time
            current = int(time.time())
            for i in range(count):
                rates[i]['time'] = current - (i * 60) # 1 min candles
                rates[i]['open'] = 1.1000
                rates[i]['high'] = 1.1050
                rates[i]['low'] = 1.0950
                rates[i]['close'] = 1.1000
            return rates

        def positions_get(self, ticket=None):
            return [] # Mock returns empty list for safety on Mac

        def order_send(self, request):
            class MockResult:
                retcode = 10009 # DONE
                order = 12345
                comment = "Mock Order Success"
            return MockResult()
            
        # Constants
        TRADE_ACTION_PENDING = 0
        TRADE_ACTION_DEAL = 1
        TRADE_ACTION_SLTP = 6
        ORDER_TYPE_BUY_LIMIT = 2
        ORDER_TYPE_SELL_LIMIT = 3
        ORDER_TYPE_BUY_STOP = 4
        ORDER_TYPE_SELL_STOP = 5
        ORDER_TYPE_BUY = 0
        ORDER_TYPE_SELL = 1
        ORDER_FILLING_RETURN = 0
        ORDER_FILLING_FOK = 1
        ORDER_FILLING_IOC = 2
        SYMBOL_FILLING_FOK = 1
        SYMBOL_FILLING_IOC = 2
        ORDER_TIME_GTC = 0
        TRADE_RETCODE_DONE = 10009
        
    mt5 = MockMT5()
    print("⚠️ WARNING: Running with MOCK MetaTrader5 (Mac Detected)")
import os
import logging
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)

class MT5Bridge:
    def __init__(self):
        try:
            val = os.getenv("MT5_LOGIN")
            self.login = int(val) if val else 0
        except:
            self.login = 0
        self.password = os.getenv("MT5_PASSWORD")
        self.server = os.getenv("MT5_SERVER")
        self.connected = False

    def get_instrument_info(self, symbol):
        """
        Returns dict with contract size and volume constraints.
        """
        if not self.connected: self.connect()
        
        found_symbol = self._find_symbol(symbol)
        if not found_symbol:
            logger.error(f"Failed to find symbol {symbol} (or any variant) for info.")
            return None

        # 1. Selection (Required for some brokers to "activate" symbol info)
        if not mt5.symbol_select(found_symbol, True):
            logger.warning(f"Failed to SELECT {found_symbol} in Market Watch. Attempting info anyway.")

        # 2. Fetch Info
        info = mt5.symbol_info(found_symbol)
        if not info:
            logger.error(f"Failed to get symbol info for {found_symbol}. MT5 Error: {mt5.last_error()}")
            return None
            
        return {
            'contract_size': info.trade_contract_size,
            'min_volume': info.volume_min,
            'max_volume': info.volume_max,
            'volume_step': info.volume_step,
            'digits': info.digits
        }

    def connect(self):
        """Initializes connection to MT5 terminal."""
        if not mt5.initialize(login=self.login, password=self.password, server=self.server):
            logger.error(f"MT5 initialization failed, error code = {mt5.last_error()}")
            self.connected = False
            return False
        
        logger.info(f"Connected to MT5: {self.login} on {self.server}")
        self.connected = True
        return True

    def _find_symbol(self, symbol):
        """Helper to find the correct symbol variant (e.g. with .a suffix or different case)."""
        # 1. Try common suffixes
        suffixes = ["", ".a", ".m", ".i", ".pro", ".x", ".z", "!", "#", "_", ".ext", ".abc"]
        variants = []
        base = symbol.split('.')[0] # Try to get base name if it has a suffix already
        
        for sfx in suffixes:
            variants.append(symbol + sfx)
            variants.append(symbol.upper() + sfx)
            if base != symbol:
                variants.append(base + sfx)
                variants.append(base.upper() + sfx)

        # Remove duplicates
        variants = list(dict.fromkeys(variants))
        
        for v in variants:
            info = mt5.symbol_info(v)
            if info is not None:
                return v

        # 2. Aggressive Fallback: Search ALL symbols for a partial match
        # Useful for symbols like "GOLD" vs "XAUUSD"
        all_symbols = mt5.symbols_get()
        if all_symbols:
            search_term = symbol.upper()
            # Special case for Gold
            if "XAU" in search_term or "GOLD" in search_term:
                potential_gold = [s.name for s in all_symbols if "XAU" in s.name.upper() or "GOLD" in s.name.upper()]
                if potential_gold:
                    # Prefer exact-ish matches
                    for p in potential_gold:
                        if search_term in p.upper() or p.upper() in search_term:
                            return p
                    return potential_gold[0]

            for s in all_symbols:
                if search_term == s.name.upper():
                    return s.name
                if search_term in s.name.upper() or s.name.upper() in search_term:
                    # Only return if it's reasonably close (e.g. "XAUUSD" in "XAUUSD.m")
                    return s.name

        return None

    def get_candles(self, symbol, timeframe, num_candles=1000):
        """
        Fetches candles from MT5 with auto-suffix matching.
        """
        if not self.connected: 
            if not self.connect(): return None

        found_symbol = self._find_symbol(symbol)
        if not found_symbol:
            logger.error(f"Failed to find symbol {symbol} (or variants) in MT5 database.")
            return None

        # Ensure symbol is selected in Market Watch (Mandatory for ticks/candles)
        if not mt5.symbol_select(found_symbol, True):
            logger.error(f"Failed to select symbol {found_symbol} in MT5 Market Watch.")
            return None

        rates = mt5.copy_rates_from_pos(found_symbol, timeframe, 0, num_candles)
        if rates is None:
            logger.error(f"Failed to get candles for {found_symbol}. Error: {mt5.last_error()}")
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    def get_tick(self, symbol):
        """Returns current bid/ask with auto-suffix matching."""
        if not self.connected: self.connect()
        
        found_symbol = self._find_symbol(symbol)
        if not found_symbol:
            logger.error(f"MT5: Symbol {symbol} NOT FOUND in MT5 database.")
            return None

        # 2. Selection (Required for ticks)
        if not mt5.symbol_select(found_symbol, True):
            logger.error(f"MT5: Failed to SELECT {found_symbol} in Market Watch.")
            return None

        # 3. Fetch Tick
        tick = mt5.symbol_info_tick(found_symbol)
        if tick:
            return {'bid': tick.bid, 'ask': tick.ask}
        
        logger.error(f"MT5: tick fetch returned None for {found_symbol}. Error: {mt5.last_error()}")
        return None

    def place_limit_order(self, symbol, order_type, price, stop_loss, take_profit, volume, comment="Ekbottlebeer Bot"):
        """
        Places a generic Limit/Stop order on MT5.
        order_type: 'buy_limit', 'sell_limit', 'buy_stop', 'sell_stop' (strings mapped to enums)
        """
        if not self.connected: self.connect()
        
        found_symbol = self._find_symbol(symbol)
        if not found_symbol:
            logger.error(f"MT5: Symbol {symbol} NOT FOUND for order placement.")
            return None

        # 1. Map string types to MT5 Constants
        type_map = {
            'buy_limit': mt5.ORDER_TYPE_BUY_LIMIT,
            'sell_limit': mt5.ORDER_TYPE_SELL_LIMIT,
            'buy_stop': mt5.ORDER_TYPE_BUY_STOP,
            'sell_stop': mt5.ORDER_TYPE_SELL_STOP,
            'market_buy': mt5.ORDER_TYPE_BUY,
            'market_sell': mt5.ORDER_TYPE_SELL
        }
        
        mt5_type = type_map.get(order_type)
        if mt5_type is None:
            logger.error(f"Invalid order type: {order_type}")
            return None

        # 2. GET SYMBOL INFO for Normalization
        info = mt5.symbol_info(found_symbol)
        if not info:
            logger.error(f"Failed to get info for {found_symbol}")
            return None

        # 3. NORMALIZE VOLUME (Step + Precision)
        step = info.volume_step
        norm_volume = round(volume / step) * step
        # Final safety round to avoid floating point ghosts
        v_decimals = str(step)[::-1].find('.')
        if v_decimals < 0: v_decimals = 2
        norm_volume = round(norm_volume, v_decimals)

        # 4. NORMALIZE PRICES (Digits)
        digits = info.digits
        norm_price = round(price, digits)
        norm_sl = round(stop_loss, digits)
        norm_tp = round(take_profit, digits)
        
        # 4b. CHECK STOPS LEVEL (Min Distance)
        # If SL/TP is too close to current price, trade will fail with 10013
        # For PENDING orders, distance is from order price.
        # For MARKET orders, distance is from current Bid/Ask.
        
        current_tick = mt5.symbol_info_tick(found_symbol)
        current_price_ref = norm_price # Default to order price for pending
        
        is_market = 'market' in order_type
        if is_market:
            # For Market execution, Price field in request should often be 0 or current Ask/Bid depending on broker
            # But usually for Python API, we set it to Ask/Bid to be safe, or 0.
            # Using specific price for Market execution can sometimes cause "Invalid Price" if market moves.
            # Best practice: Set price to 0.0 for DEAL action if it's instant execution, 
            # UNLESS it's "Market Execution" mode where SL/TP must be empty initially.
            # Here we assume we can send SL/TP with Valid Price.
            current_price_ref = current_tick.ask if 'buy' in order_type else current_tick.bid
            norm_price = current_price_ref # Update target price to current for calculation check
            
        stops_level_points = info.trade_stops_level
        point_size = info.point
        min_dist = stops_level_points * point_size
        
        # Verify SL distance
        if abs(norm_price - norm_sl) < min_dist:
            logger.warning(f"MT5: SL too close! Dist: {abs(norm_price - norm_sl):.5f} < Min: {min_dist:.5f}. Adjusting...")
            # Adjust SL to be valid
            if 'buy' in order_type: # Long: SL below
                norm_sl = norm_price - min_dist - point_size
            else: # Short: SL above
                norm_sl = norm_price + min_dist + point_size
            norm_sl = round(norm_sl, digits)
            
        # 5. DETECT FILLING MODE (Robust)
        # Some brokers report FOK support but reject it. We default to IOC or FOK based on flags.
        # If nothing set, use RETURN (default).
        filling = mt5.ORDER_FILLING_FOK # Default preference for scalping
        
        # Check support flags
        fill_flags = info.filling_mode
        if fill_flags & mt5.ORDER_FILLING_FOK:
            filling = mt5.ORDER_FILLING_FOK
        elif fill_flags & mt5.ORDER_FILLING_IOC:
            filling = mt5.ORDER_FILLING_IOC
        else:
            filling = mt5.ORDER_FILLING_RETURN

        action = mt5.TRADE_ACTION_PENDING if 'limit' in order_type or 'stop' in order_type else mt5.TRADE_ACTION_DEAL
        
        if is_market:
            # OPTIMIZATION: For "Market Execution", MT5 requires price to be 0.0 for many brokers.
            # Sending a specific price (even current) can cause "Invalid Price" or "Off Quotes".
            norm_price = 0.0
        
        request = {
            "action": action,
            "symbol": found_symbol,
            "volume": norm_volume,
            "type": mt5_type,
            "price": norm_price,
            "sl": norm_sl,
            "tp": norm_tp,
            "deviation": 50, # Increased deviation for slippage
            "magic": 123456,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }
        
        logger.info(f"MT5 sending: {request}")
        
        result = mt5.order_send(request)
        if not result or result.retcode != mt5.TRADE_RETCODE_DONE:
            err_code = result.retcode if result else "NO_RESULT"
            err_msg = result.comment if result else "Unknown Error"
            
            # RETRY LOGIC: Check for recoverable errors first
            # 10030 = Unsupported Filling Mode, 10013 = Invalid Request (sometimes filling related)
            if err_code in [10030, 10013, 10014, 10015, 10029]: 
                logger.info(f"MT5: Broker requires diff filling mode (Code {err_code}). Adjusting...")
                
                for alt_filling in [mt5.ORDER_FILLING_IOC, mt5.ORDER_FILLING_FOK, mt5.ORDER_FILLING_RETURN]:
                    if alt_filling == filling: continue
                    
                    request["type_filling"] = alt_filling
                    logger.info(f"MT5: Retrying with filing mode: {alt_filling}")
                    
                    retry_res = mt5.order_send(request)
                    if retry_res and retry_res.retcode == mt5.TRADE_RETCODE_DONE:
                        logger.info(f"✅ Order Success on Retry (Mode {alt_filling})! Ticket: {retry_res.order}")
                        return retry_res.order
                    else:
                        r_code = retry_res.retcode if retry_res else "None"
                        # Keep this low noise unless all fail
            
            # If we get here, all retries failed OR it was a fatal error
            logger.error(f"MT5 Order Failed: {err_code} - {err_msg}")
            return None
            
        logger.info(f"Order Placed on MT5: {found_symbol} {order_type} @ {norm_price}, Ticket: {result.order}")
        return result.order

    def modify_order(self, ticket, sl=None, tp=None, price=None):
        """Modifies an existing order or position (SL/TP)."""
        if not self.connected: self.connect()
        
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket, # For active positions
            # "order": ticket # For pending orders? MT5 uses same field often or requires correct action
            # TRADE_ACTION_SLTP works on Positions. 
            # If modifying a pending order, use TRADE_ACTION_MODIFY.
            # We assume active position for Trailing SL logic.
        }
        
        if sl: request["sl"] = float(sl)
        if tp: request["tp"] = float(tp)
        
        import time
        attempts = 3
        for i in range(attempts):
            result = mt5.order_send(request)
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                logger.info(f"Order {ticket} Modified. SL: {sl}")
                return True
            else:
                logger.warning(f"Modify Attempt {i+1} Failed: {result.comment}. Retrying...")
                time.sleep(1)
                
        logger.error(f"Modify Failed after {attempts} attempts: {result.comment}")
        return False

    def close_position(self, ticket, pct=1.0, qty=None):
        """Closes a position (or partial). 'qty' arg is ignored (compatibility)."""
        if not self.connected: self.connect()
        
        # 1. Get position details (volume)
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            logger.warning(f"Position {ticket} not found to close.")
            return False
            
        pos = positions[0]
        close_vol = pos.volume * pct
        
        # Determine close type (Opposite)
        close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = mt5.symbol_info_tick(pos.symbol).bid if close_type == mt5.ORDER_TYPE_SELL else mt5.symbol_info_tick(pos.symbol).ask
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": close_vol,
            "type": close_type,
            "position": ticket,
            "price": price,
            "deviation": 20,
            "magic": 123456,
            "comment": f"Close {pct*100}%",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_RETURN,
        }
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Close Failed: {result.comment}")
            return False
            
        logger.info(f"Position {ticket} Closed ({pct*100}%)")
        return True

    def get_all_positions(self):
        """Returns list of all active positions."""
        if not self.connected: self.connect()
        
        try:
            positions = mt5.positions_get()
            if positions:
                active = []
                for p in positions:
                    active.append({
                        'symbol': p.symbol,
                        'ticket': p.ticket,
                        'size': p.volume,
                        'type': p.type
                    })
                return active
            return []
        except Exception as e:
            logger.error(f"Failed to get MT5 positions: {e}")
            return []

    def get_balance(self):
        if not self.connected: self.connect()
        account_info = mt5.account_info()
        if account_info:
            return account_info.balance
        return 0.0

    def shutdown(self):
        mt5.shutdown()
        self.connected = False

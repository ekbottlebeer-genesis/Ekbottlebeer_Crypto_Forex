# src/bridges/mt5_bridge.py
import MetaTrader5 as mt5
import os
import logging
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)

class MT5Bridge:
    def __init__(self):
        self.login = int(os.getenv("MT5_LOGIN", 0))
        self.password = os.getenv("MT5_PASSWORD")
        self.server = os.getenv("MT5_SERVER")
        self.connected = False

    def get_instrument_info(self, symbol):
        """
        Returns dict with contract size and volume constraints.
        """
        if not self.connected: self.connect()
        
        info = mt5.symbol_info(symbol)
        if not info:
            logger.error(f"Failed to get symbol info for {symbol}")
            return None
            
        return {
            'contract_size': info.trade_contract_size,
            'min_volume': info.volume_min,
            'max_volume': info.volume_max,
            'volume_step': info.volume_step
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

    def get_candles(self, symbol, timeframe, num_candles=1000):
        """
        Fetches candles from MT5.
        timeframe: e.g., mt5.TIMEFRAME_M5, mt5.TIMEFRAME_H1
        num_candles: Quantity to fetch.
        """
        if not self.connected: 
            if not self.connect(): return None

        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, num_candles)
        if rates is None:
            logger.error(f"Failed to get candles for {symbol}")
            return None

        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df

    def place_limit_order(self, symbol, order_type, price, stop_loss, take_profit, volume, comment="Ekbottlebeer Bot"):
        """
        Places a generic Limit/Stop order on MT5.
        order_type: 'buy_limit', 'sell_limit', 'buy_stop', 'sell_stop' (strings mapped to enums)
        """
        if not self.connected: self.connect()
        
        # Map string types to MT5 Constants
        # Note: Standard MT5 order types:
        # ORDER_TYPE_BUY_LIMIT, ORDER_TYPE_SELL_LIMIT
        # ORDER_TYPE_BUY_STOP, ORDER_TYPE_SELL_STOP
        
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

        # Check symbol info for volume steps / filling modes if needed
        # For simplicity, we assume standard filling (ORDER_FILLING_IOC or FOK depending on broker)
        
        request = {
            "action": mt5.TRADE_ACTION_PENDING if 'limit' in order_type or 'stop' in order_type else mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": mt5_type,
            "price": float(price),
            "sl": float(stop_loss),
            "tp": float(take_profit),
            "deviation": 20,
            "magic": 123456,
            "comment": comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_RETURN,
        }
        
        # If market order, price might need to be current ask/bid, although usually ignored or 0 for market, 
        # but required to be valid for send.
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Order Send Failed: {result.retcode} - {result.comment}")
            return None
            
        logger.info(f"Order Placed on MT5: {symbol} {order_type} @ {price}, Ticket: {result.order}")
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
        
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            logger.error(f"Modify Failed: {result.comment}")
            return False
            
        logger.info(f"Order {ticket} Modified. SL: {sl}")
        return True

    def close_position(self, ticket, pct=1.0):
        """Closes a position (or partial)."""
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

    def get_balance(self):
        if not self.connected: self.connect()
        account_info = mt5.account_info()
        if account_info:
            return account_info.balance
        return 0.0

    def shutdown(self):
        mt5.shutdown()
        self.connected = False

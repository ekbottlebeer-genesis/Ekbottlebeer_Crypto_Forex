# src/bridges/bybit_bridge.py
from pybit.unified_trading import HTTP
import os
import logging
import pandas as pd

logger = logging.getLogger(__name__)

class BybitBridge:
    def __init__(self):
        api_key = os.getenv("BYBIT_API_KEY")
        api_secret = os.getenv("BYBIT_API_SECRET")
        testnet = os.getenv("BYBIT_TESTNET", "True").lower() == "true"
        
        self.session = None
        if api_key and api_secret:
            try:
                self.session = HTTP(
                    testnet=testnet,
                    api_key=api_key,
                    api_secret=api_secret
                )
                logger.info(f"Bybit Session Initialized (Testnet: {testnet})")
            except Exception as e:
                logger.error(f"Failed to initialize Bybit session: {e}")

    def get_instrument_info(self, symbol):
        """
        Returns constraints. Bybit Linear usually 1 contract = 1 Coin (or unit).
        We should fetch 'lotSizeFilter' from instruments-info if strict.
        For demo/speed, we assume standard steps (e.g. 0.001 for BTC).
        """
        # Ideally fetch from self.session.get_instruments_info(...)
        # Stub for robustness:
        return {
            'contract_size': 1.0, 
            'min_volume': 0.001, # Safe default for crypto
            'max_volume': 1000.0,
            'volume_step': 0.001 
        }

    def get_candles(self, symbol, timeframe, num_candles=200):
        """
        Fetch kline data.
        Standardized Interface:
        timeframe: Bybit interval string ('1', '5', '60', 'D')
        num_candles: Number of candles to fetch (mapped to 'limit')
        """
        if not self.session:
            logger.warning("Bybit session not active.")
            return None

        try:
            response = self.session.get_kline(
                category="linear",
                symbol=symbol,
                interval=timeframe,
                limit=num_candles
            )
            # Process response to DataFrame
            if response['retCode'] == 0:
                data = response['result']['list']
                # Bybit returns: [startTime, open, high, low, close, volume, turnover]
                # Note: list is in reverse order (newest first)
                df = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
                df['time'] = pd.to_datetime(pd.to_numeric(df['time']), unit='ms')
                df = df.astype({'open': 'float', 'high': 'float', 'low': 'float', 'close': 'float', 'volume': 'float'})
                return df.iloc[::-1] # Reverse to have oldest first
            else:
                logger.error(f"Bybit API Error: {response['retMsg']}")
                return None
        except Exception as e:
            logger.error(f"Error fetching Bybit candles: {e}")
            return None
    def place_order(self, symbol, side, order_type, qty, price=None, stop_loss=None, take_profit=None):
        """
        Places an order on Bybit (Unified Trading).
        side: 'Buy' or 'Sell'
        order_type: 'Limit' or 'Market'
        """
        if not self.session: return None
        
        try:
            params = {
                 "category": "linear",
                 "symbol": symbol,
                 "side": side,
                 "orderType": order_type,
                 "qty": str(qty),
            }
            if price: params["price"] = str(price)
            if stop_loss: params["stopLoss"] = str(stop_loss)
            if take_profit: params["takeProfit"] = str(take_profit)
            
            response = self.session.place_order(**params)
            
            if response['retCode'] == 0:
                order_id = response['result']['orderId']
                logger.info(f"Bybit Order Placed: {symbol} {side} {qty} @ {price}. ID: {order_id}")
                return order_id
            else:
                logger.error(f"Bybit Order Failed: {response['retMsg']}")
                return None
                
        except Exception as e:
            logger.error(f"Bybit Place Error: {e}")
            return None

    def modify_order(self, order_id=None, symbol=None, sl=None, tp=None):
        """
        Modifies order or position SL/TP.
        For active positions in Unified Account, usually setTradingStop is used.
        """
        if not self.session: return False
        
        try:
            # Set Trading Stop (for Positions)
            params = {
                "category": "linear",
                "symbol": symbol,
            }
            if sl: params["stopLoss"] = str(sl)
            if tp: params["takeProfit"] = str(tp)
            # if order_id: params["orderId"] = order_id # setTradingStop applies to position usually, not specific order ID unless pending
            
            # Note: set_trading_stop is for active positions. 
            # amend_order is for pending orders.
            # Assuming we are trailing an active position:
            response = self.session.set_trading_stop(**params)
            
            if response['retCode'] == 0:
                logger.info(f"Bybit Position Modified: {symbol} SL={sl}")
                return True
            else:
                logger.error(f"Bybit Modify Failed: {response['retMsg']}")
                return False
        except Exception as e:
            logger.error(f"Bybit Modify Error: {e}")
            return False

    def close_position(self, symbol, qty=None):
        """Closes (market) position."""
        if not self.session: return False
        # To close, we place an opposite order or use specific close endpoint if available?
        # Standard: Place Market Reduce-Only Order.
        # Or place command "close all"
        
        # Simple implementation: Need current position side to know which way to close.
        # For this stub, we won't auto-detect side. Assuming Caller knows.
        # Ideally, we fetch position first.
        return False # TODO: Implement fetch position -> place reduce-only order

    def get_balance(self):
        if not self.session: return 0.0
        try:
             resp = self.session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
             if resp['retCode'] == 0:
                 # Parse equity
                 return float(resp['result']['list'][0]['totalEquity'])
        except:
             return 0.0
        return 0.0

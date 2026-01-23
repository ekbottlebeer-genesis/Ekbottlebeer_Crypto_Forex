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
        
        # FORCE RE-LOAD check for BYBIT_DEMO
        demo_trading = os.getenv("BYBIT_DEMO", "False").strip().lower() == "true"
        
        if demo_trading:
            logger.info("Configuring for Bybit DEMO Trading (api-demo.bybit.com)...")
            testnet = False 
        else:
            testnet = os.getenv("BYBIT_TESTNET", "True").strip().lower() == "true"
        
        # Log detected values for visibility
        logger.info(f"PROBING: BYBIT_DEMO env is '{os.getenv('BYBIT_DEMO')}' -> demo={demo_trading}")
        logger.info(f"PROBING: BYBIT_TESTNET env is '{os.getenv('BYBIT_TESTNET')}' -> testnet={testnet}")
        
        self.session = None
        self._instruments_cache = {} 
        if api_key and api_secret:
            try:
                # Construct args
                kwargs = {
                    'testnet': testnet,
                    'api_key': api_key,
                    'api_secret': api_secret
                }
                
                if demo_trading:
                    # In pybit V5, use demo=True for Demo Trading
                    kwargs['demo'] = True
                
                self.session = HTTP(**kwargs)
                logger.info(f"Bybit Session Initialized (Testnet: {testnet}, Demo: {demo_trading})")
            except Exception as e:
                logger.error(f"Failed to initialize Bybit session: {e}")

    def get_instrument_info(self, symbol):
        """
        Fetches real instrument info from Bybit and caches it.
        """
        if symbol in self._instruments_cache:
            return self._instruments_cache[symbol]

        if not self.session:
            return {'contract_size': 1.0, 'min_volume': 0.001, 'max_volume': 1000.0, 'volume_step': 0.001}

        try:
            resp = self.session.get_instruments_info(category="linear", symbol=symbol)
            if resp['retCode'] == 0:
                item = resp['result']['list'][0]
                filters = item['lotSizeFilter']
                info = {
                    'contract_size': 1.0,
                    'min_volume': float(filters['minOrderQty']),
                    'max_volume': float(filters['maxOrderQty']),
                    'volume_step': float(filters['qtyStep']),
                    'price_precision': int(item['priceScale'])
                }
                self._instruments_cache[symbol] = info
                return info
        except Exception as e:
            logger.error(f"Error fetching Bybit instrument info for {symbol}: {e}")
        
        return {'contract_size': 1.0, 'min_volume': 0.001, 'max_volume': 1000.0, 'volume_step': 0.001}

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
                if not data:
                    logger.warning(f"Bybit: No candles found for {symbol}. Check if symbol is correct and you have trading permissions.")
                    return None
                # Bybit returns: [startTime, open, high, low, close, volume, turnover]
                # Note: list is in reverse order (newest first)
                df = pd.DataFrame(data, columns=['time', 'open', 'high', 'low', 'close', 'volume', 'turnover'])
                df['time'] = pd.to_datetime(pd.to_numeric(df['time']), unit='ms')
                df = df.astype({'open': 'float', 'high': 'float', 'low': 'float', 'close': 'float', 'volume': 'float'})
                return df.iloc[::-1] # Reverse to have oldest first
            else:
                msg = response['retMsg']
                logger.error(f"Bybit API Error: {msg}")
                if "10001" in str(response['retCode']):
                    logger.error("TIP: Parameter error. Check if BYBIT_DEMO=True matches your account type.")
                return None
        except Exception as e:
            logger.error(f"Error fetching Bybit candles: {e}")
            return None
    def get_tick(self, symbol):
        """Returns current bid/ask."""
        if not self.session: return None
        try:
             resp = self.session.get_tickers(category="linear", symbol=symbol)
             if resp['retCode'] == 0:
                 res = resp['result']['list'][0]
                 return {'bid': float(res['bid1Price']), 'ask': float(res['ask1Price'])}
        except:
             return None
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
            # Retry Loop
            import time
            for i in range(3):
                try:
                    response = self.session.set_trading_stop(**params)
                    if response['retCode'] == 0:
                        logger.info(f"Bybit Position Modified: {symbol} SL={sl}")
                        return True
                    else:
                         logger.warning(f"Bybit Modify Attempt {i+1} Failed: {response['retMsg']}")
                         time.sleep(1)
                except Exception as e:
                    logger.warning(f"Bybit Modify Exception: {e}")
                    time.sleep(1)
            
            return False
        except Exception as e:
            logger.error(f"Bybit Modify Error: {e}")
            return False

    def close_position(self, symbol, qty=None):
        """
        Closes (market) position.
        """
        if not self.session: return False
        
        try:
            # 1. Determine Position Side/Size if not provided
            # We need to know current side to Sell(Close Long) or Buy(Close Short)
            # Fetch position
            pos_resp = self.session.get_positions(category="linear", symbol=symbol)
            if pos_resp['retCode'] != 0:
                logger.error(f"Failed to fetch position for {symbol}")
                return False
                
            positions = pos_resp['result']['list']
            target_pos = None
            for p in positions:
                if float(p['size']) > 0:
                    target_pos = p
                    break
            
            if not target_pos:
                logger.warning(f"No position found to close for {symbol}")
                return False
                
            side = target_pos['side'] # 'Buy' or 'Sell'
            size = float(target_pos['size'])
            
            # Determine Close Side
            close_side = 'Sell' if side == 'Buy' else 'Buy'
            
            # Use provided qty or full close
            close_qty = str(qty) if qty else str(size)
            
            # 2. Place Reduce-Only Market Order
            resp = self.session.place_order(
                category="linear",
                symbol=symbol,
                side=close_side,
                orderType="Market",
                qty=close_qty,
                reduceOnly=True
            )
            
            if resp['retCode'] == 0:
                 logger.info(f"Bybit Position Closed: {symbol} {close_side} {close_qty}")
                 return True
            else:
                 logger.error(f"Bybit Close Failed: {resp['retMsg']}")
                 return False
                 
        except Exception as e:
            logger.error(f"Bybit Close Error: {e}")
            return False

    def get_balance(self):
        if not self.session: return 0.0
        try:
             # Standard: Unified Trading Account / Demo
             resp = self.session.get_wallet_balance(accountType="UNIFIED", coin="USDT")
             
             # PHASE 16 ULTRA-VERBOSE TRACING
             logger.info(f"DEBUG: Bybit Full Balance Response: {resp}")
             
             if resp['retCode'] == 0:
                 acc_list = resp['result']['list']
                 if acc_list:
                     acc = acc_list[0]
                     # Try to get balance from various keys (depending on Bybit sub-type)
                     equity = float(acc.get('totalEquity', 0))
                     if equity > 0: return equity
                     
                     # Check coin list
                     coin_list = acc.get('coin', [])
                     for c in coin_list:
                         if c['coin'] == 'USDT':
                             return float(c.get('equity', c.get('walletBalance', 0)))
             
             # FALLBACK: Try fetching without specifying USDT (Get all and look for max)
             gen_resp = self.session.get_wallet_balance(accountType="UNIFIED")
             if gen_resp['retCode'] == 0 and gen_resp['result']['list']:
                 gen_acc = gen_resp['result']['list'][0]
                 gen_equity = float(gen_acc.get('totalEquity', 0))
                 if gen_equity > 0: return gen_equity
                 
             return 0.0
        except Exception as e:
             logger.error(f"Error fetching Bybit balance: {e}")
             return 0.0

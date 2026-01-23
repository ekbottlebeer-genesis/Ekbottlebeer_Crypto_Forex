
import pandas as pd
import numpy as np
import logging
import datetime
import os
from src.strategy.smc_logic import SMCLogic
from src.utils.visualizer import Visualizer

# Configure logging for backtest
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BacktestEngine")

class Loader:
    """CSV Data Loader & Resampler"""
    @staticmethod
    def load_csv(filepath):
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Data file not found: {filepath}")
        
        # Determine separator (MT5 often uses tab)
        # Try reading a few lines to sniff
        try:
             df = pd.read_csv(filepath, sep='\t')
             if '<DATE>' not in df.columns:
                 # Fallback to comma if standard keys not found
                 df = pd.read_csv(filepath)
        except:
             df = pd.read_csv(filepath)

        df.columns = [c.replace('<','').replace('>','').lower() for c in df.columns]
        
        # MT5: date + time columns
        if 'date' in df.columns and 'time' in df.columns:
            # Combine
            df['timestamp'] = pd.to_datetime(df['date'] + ' ' + df['time'])
            df.set_index('timestamp', inplace=True)
            df.drop(columns=['date', 'time'], inplace=True)
        elif 'time' in df.columns:
             # Basic Format
             df['time'] = pd.to_datetime(df['time'])
             df.set_index('time', inplace=True)
             
        # Rename tickvol -> volume if needed
        if 'tickvol' in df.columns:
            df.rename(columns={'tickvol': 'volume'}, inplace=True)
        elif 'vol' in df.columns:
            df.rename(columns={'vol': 'volume'}, inplace=True)
            
        df.index.name = 'time'
        return df.sort_index()

    @staticmethod
    def resample_data(df, timeframe):
        """
        Resamples M1 data to target timeframe (e.g., '5min', '1H').
        """
        agg_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }
        resampled = df.resample(timeframe).agg(agg_dict).dropna()
        # Reset index to keep 'time' as column for consistency with live logic
        resampled = resampled.reset_index()
        return resampled

class SimulatedBroker:
    """Tracks Balance, Positions, and Equity Curve"""
    def __init__(self, initial_balance=10000, leverage=100, slippage=0.0, commission_type='fixed', commission_value=0.0, lot_size=100):
        self.balance = initial_balance
        self.leverage = leverage
        self.slippage = slippage
        self.commission_type = commission_type
        self.commission_value = commission_value
        self.lot_size = lot_size
        
        self.positions = [] 
        self.trade_history = []
        self.equity_curve = []

    def get_price_with_slippage(self, price, direction):
        if direction == 'buy':
            return price + self.slippage
        return price - self.slippage

    def place_order(self, symbol, side, qty, entry_price, sl, tp, time):
        # Calc comm:
        comm_cost = 0
        
        if self.commission_type == 'fixed_per_lot':
            # e.g., $7 per lot (round turn or per side?)
            # Usually quoted as "RT" (Round Turn). We charge half here, or full?
            # Let's charge FULL on entry for simplicity in backtest.
            lots = qty / self.lot_size
            comm_cost = lots * self.commission_value
            
        elif self.commission_type == 'percentage':
            # e.g., 0.05% of Notional
            notional = qty * entry_price
            comm_cost = notional * (self.commission_value / 100)
            
        elif self.commission_type == 'fixed':
            # Flat fee per trade? Or per unit?
            # If value is 0.0, it's 0.
            comm_cost = qty * self.commission_value # Assuming per unit if just 'fixed' often implies spread only.
        
        real_entry = self.get_price_with_slippage(entry_price, side)
        
        trade = {
            'id': len(self.trade_history) + len(self.positions) + 1,
            'symbol': symbol,
            'direction': side,
            'qty': qty,
            'entry_price': real_entry,
            'sl': sl,
            'tp': tp,
            'open_time': time,
            'commission': comm_cost
        }
        self.positions.append(trade)
        return trade

    def check_sl_tp(self, current_candle):
        """
        Did High hit SL/TP? Did Low hit SL/TP?
        Checks M1 bars for intra-candle precision.
        """
        closed_trades = []
        
        for trade in self.positions[:]:
            # CHECK SL
            sl_hit = False
            if trade['direction'] == 'buy':
                if current_candle['low'] <= trade['sl']:
                    exit_price = trade['sl'] # Assume slippage on SL too strictly? For now exact.
                    sl_hit = True
            else: # Sell
                if current_candle['high'] >= trade['sl']:
                    exit_price = trade['sl']
                    sl_hit = True
            
            if sl_hit:
                self.close_trade(trade, exit_price, current_candle['time'], 'SL')
                continue

            # CHECK TP
            tp_hit = False
            if trade['direction'] == 'buy':
                if current_candle['high'] >= trade['tp']:
                    exit_price = trade['tp']
                    tp_hit = True
            else: # Sell
                if current_candle['low'] <= trade['tp']:
                    exit_price = trade['tp']
                    tp_hit = True
            
            if tp_hit:
                self.close_trade(trade, exit_price, current_candle['time'], 'TP')
                continue

    def close_trade(self, trade, exit_price, time, reason):
        # Commission on exit
        comm_cost = 0
        
        if self.commission_type == 'fixed_per_lot':
             # Already charged full round turn on entry.
             comm_cost = 0 
             
        elif self.commission_type == 'percentage':
             # Charge percentage on exit value
             notional = trade['qty'] * exit_price
             comm_cost = notional * (self.commission_value / 100)
             
        elif self.commission_type == 'fixed':
             comm_cost = self.commission_value * trade['qty'] # If per unit
        
        if trade['direction'] == 'buy':
            gross_pnl = (exit_price - trade['entry_price']) * trade['qty']
        else:
            gross_pnl = (trade['entry_price'] - exit_price) * trade['qty']
            
        net_pnl = gross_pnl - trade['commission'] - comm_cost
        
        self.balance += net_pnl
        
        # Log
        closed = trade.copy()
        closed['exit_price'] = exit_price
        closed['close_time'] = time
        closed['pnl'] = net_pnl
        closed['reason'] = reason
        
        self.trade_history.append(closed)
        self.positions.remove(trade)

class SilentReporter:
    """Redirects alerts to a log file"""
    def __init__(self, filename='backtest_events.log'):
        self.filename = filename
        # Clear log
        with open(filename, 'w') as f:
            f.write(f"--- Backtest Started: {datetime.datetime.now()} ---\n")

    def send_message(self, msg):
        with open(self.filename, 'a') as f:
            f.write(f"[MSG] {msg}\n")
            
    def send_photo(self, path, caption=""):
        with open(self.filename, 'a') as f:
            f.write(f"[IMG] {path} | {caption}\n")

class BacktestEngine:
    MODE = 'BACKTEST'
    
    # Define Asset Profiles
    ASSET_CONFIG = {
        'GOLD': {
            'file': 'Gold.csv',
            'symbol': 'XAUUSD',
            'commission_type': 'fixed', # Fixed amount per unit/lot
            'commission_value': 0.0,    # $0 (Spread based)
            'slippage': 0.10,           # $0.10 per unit
            'lot_size': 100             # 1 Standard Lot = 100oz
        },
        'FOREX': {
            'file': 'Forex.csv',
            'symbol': 'EURUSD',
            'commission_type': 'fixed_per_lot',
            'commission_value': 7.0,    # $7 per round turn lot
            'slippage': 0.0001,         # 1 pip (Standard pip = 0.0001)
            'lot_size': 100000          # 1 Standard Lot = 100,000 units
        },
        'CRYPTO': {
            'file': 'Crypto.csv',
            'symbol': 'BTCUSD',
            'commission_type': 'percentage',
            'commission_value': 0.05,   # 0.05% Taker Fee
            'slippage': 5.0,            # $5.00 slippage on BTC
            'lot_size': 1               # 1 Unit = 1 BTC
        }
    }

    def __init__(self, asset_class='GOLD'):
        if asset_class not in self.ASSET_CONFIG:
            raise ValueError(f"Invalid Asset Class. Options: {list(self.ASSET_CONFIG.keys())}")
        
        config = self.ASSET_CONFIG[asset_class]
        self.symbol = config['symbol']
        data_path = config['file']
        
        logger.info(f"Initializing Backtest for {asset_class} ({self.symbol})")
        
        self.df_m1 = Loader.load_csv(data_path) # Master M1 Data
        
        # Initialize Broker with Asset Specifics
        self.broker = SimulatedBroker(
            initial_balance=10000,
            slippage=config['slippage'],
            commission_type=config['commission_type'],
            commission_value=config['commission_value'],
            lot_size=config['lot_size']
        )
        
        self.reporter = SilentReporter()
        self.strategy = SMCLogic()
        self.visualizer = Visualizer()
        
        # State
        self.htf_candles = pd.DataFrame()
        self.ltf_candles = pd.DataFrame()
        self.trades_taken = 0
        
    def run(self):
        logger.info(f"Starting Backtest on {self.symbol}...")
        logger.info(f"Data range: {self.df_m1.index[0]} to {self.df_m1.index[-1]}")
        
        logger.info("Pre-sampling HTF(1H) and LTF(5min) for lookup...")
        self.df_h1 = Loader.resample_data(self.df_m1, '1H').set_index('time')
        self.df_m5 = Loader.resample_data(self.df_m1, '5min').set_index('time')
        
        # Calculate RSI on M5
        self.df_m5['rsi'] = self.strategy.calculate_rsi(self.df_m5['close'], 14)
        
        # Setup Variables
        sweep_state = {'swept': False}
        total_bars = len(self.df_m1)
        
        print(f"Processing {total_bars} M1 bars...")
        
        for i, (current_time, row) in enumerate(self.df_m1.iterrows()):
            if i % 10000 == 0:
                print(f"{int(i/total_bars*100)}%...", end="", flush=True)
                
            # 1. Update Broker (Check SL/TP on this M1 bar)
            current_price_dict = {'time': current_time, 'open': row['open'], 'high': row['high'], 
                                  'low': row['low'], 'close': row['close']}
            self.broker.check_sl_tp(current_price_dict)
            
            # Context Lookup
            valid_h1_mask = self.df_h1.index < current_time
            valid_m5_mask = self.df_m5.index < current_time

            # Retrieve recent history
            # Optimization: slicing is faster than boolean install usually, but we need dynamic cutoff
            # Actually, using searchsorted on index is fastest, but let's stick to simple masking for now
            # To optimize: Maintain a pointer?
            # For robustness, we'll keep the mask logic but maybe optimize later if too slow.
            
            htf_slice = self.df_h1[valid_h1_mask].tail(55).reset_index()
            ltf_slice = self.df_m5[valid_m5_mask].tail(200).reset_index()
            
            if len(htf_slice) < 20 or len(ltf_slice) < 50:
                continue
                
            # --- BLOCK 2.1: HTF Sweep ---
            new_sweep = self.strategy.detect_htf_sweeps(htf_slice)
            if new_sweep['swept']:
                sweep_state = new_sweep

            # --- BLOCK 2.2: LTF MSS ---
            if sweep_state['swept']:
                mss_result = self.strategy.detect_mss(ltf_slice, sweep_state['side'], sweep_state['sweep_candle_time'])
                
                if mss_result['mss']:
                    # --- BLOCK 2.3: FVG Entry ---
                    direction = 'bullish' if sweep_state['side'] == 'sell_side' else 'bearish'
                    fvgs = self.strategy.find_fvg(ltf_slice, direction, mss_result['leg_high'], mss_result['leg_low'])
                    
                    if fvgs:
                        # RSI Confluence Check
                        current_rsi = ltf_slice.iloc[-1]['rsi']
                        rsi_ok = False
                        if direction == 'bullish':
                            if 40 <= current_rsi <= 70: rsi_ok = True
                        else: # Bearish
                            if 30 <= current_rsi <= 60: rsi_ok = True
                            
                        if rsi_ok:
                             self.execute_trade(direction, fvgs[0], current_price_dict, sweep_state, mss_result, current_rsi)
                        
                        # Reset Sweep
                        sweep_state = {'swept': False}

        print("\nDone!")
        self.generate_report()

    def execute_trade(self, direction, fvg, current_bar, sweep, mss, rsi=None):
        # Calc SL/TP
        if direction == 'bullish': # Long
            sl = sweep['level'] - 0.0005 # Buffer (need to make asset specific?)
            entry = fvg['entry']
            risk = entry - sl
            if risk <= 0: return # Invalid
            tp = entry + (risk * 2.0) # 1:2 RR
            side = 'buy'
        else: # Short
            sl = sweep['level'] + 0.0005
            entry = fvg['entry']
            risk = sl - entry
            if risk <= 0: return
            tp = entry - (risk * 2.0)
            side = 'sell'
            
        # Position Size (Fixed Risk $100)
        risk_amt = 100
        qty = risk_amt / risk 
        
        # Place Order
        trade = self.broker.place_order(self.symbol, side, qty, entry, sl, tp, current_bar['time'])
        
        rsi_str = f" | RSI: {rsi:.1f}" if rsi else ""
        msg = f"🆕 TRADE: {side.upper()} @ {entry:.5f} | SL: {sl:.5f} | TP: {tp:.5f}{rsi_str}"
        self.reporter.send_message(msg)
        self.trades_taken += 1
        
        # Audit Image (Optional)
        # ... logic for visualizer ...

    def generate_report(self):
        trades = pd.DataFrame(self.broker.trade_history)
        if trades.empty:
            print("No trades generated.")
            return
            
        total_trades = len(trades)
        wins = trades[trades['pnl'] > 0]
        losses = trades[trades['pnl'] <= 0]
        
        win_rate = len(wins) / total_trades * 100 if total_trades > 0 else 0
        net_pnl = trades['pnl'].sum()
        
        report = f"""
        === BACKTEST REPORT ===
        Asset: {self.symbol}
        Total Trades: {total_trades}
        Net PnL: ${net_pnl:.2f}
        Win Rate: {win_rate:.1f}%
        Avg Win: ${wins['pnl'].mean():.2f} if not wins.empty else 0
        Avg Loss: ${losses['pnl'].mean():.2f} if not losses.empty else 0
        Final Balance: ${self.broker.balance:.2f}
        =======================
        """
        print(report)
        self.reporter.send_message(report)
        
        output_file = f"backtest_results_{self.symbol}.csv"
        trades.to_csv(output_file)
        print(f"Detailed results saved to {output_file}")

if __name__ == "__main__":
    import sys
    
    print("=== Multi-Asset Backtester ===")
    print("Available Assets: GOLD, FOREX, CRYPTO")
    
    asset_choice = 'GOLD' # Default
    if len(sys.argv) > 1:
        asset_choice = sys.argv[1].upper()
        
    try:
        engine = BacktestEngine(asset_choice)
        engine.run()
    except Exception as e:
        print(f"Error: {e}")
        print("Usage: python backtest_module.py [GOLD|FOREX|CRYPTO]")

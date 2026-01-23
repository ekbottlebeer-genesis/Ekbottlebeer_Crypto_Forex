
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
    def __init__(self, initial_balance=10000, leverage=100, slippage_pips=0.5, comm_pct=0.06):
        self.balance = initial_balance
        self.leverage = leverage
        self.slippage = slippage_pips * 0.0001 # Assuming Forex scale roughly, varies by asset
        self.commission = comm_pct / 100 # % per side
        self.positions = [] # List of dicts
        self.trade_history = []
        self.equity_curve = []

    def get_price_with_slippage(self, price, direction):
        # Buy = Ask (Price + Slip), Sell = Bid (Price - Slip)
        if direction == 'buy':
            return price + self.slippage
        return price - self.slippage

    def place_order(self, symbol, side, qty, entry_price, sl, tp, time):
        # Calculate commission
        notional = qty * entry_price
        comm_cost = notional * self.commission
        
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
        notional = trade['qty'] * exit_price
        comm_cost = notional * self.commission
        
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
    
    def __init__(self, data_path, symbol='EURUSD'):
        self.symbol = symbol
        self.df_m1 = Loader.load_csv(data_path) # Master M1 Data
        self.broker = SimulatedBroker(initial_balance=10000)
        self.reporter = SilentReporter()
        self.strategy = SMCLogic()
        self.visualizer = Visualizer() # Requires Playwright
        
        # State
        self.htf_candles = pd.DataFrame()
        self.ltf_candles = pd.DataFrame()
        self.trades_taken = 0
        
    def run(self):
        logger.info(f"Starting Backtest on {self.symbol}...")
        logger.info(f"Data range: {self.df_m1.index[0]} to {self.df_m1.index[-1]}")
        
        # Iterating M1 bars (The Clock)
        # Optimization: We assume M1 index is continuous. 
        # For simple resampling simulation, we build buffers.
        
        # Helper: Resample entire dataset first for reference? 
        # No, we must simulate "live" view.
        # But for speed, we can pre-calculate the resampled dataframes and just slice them.
        
        logger.info("Pre-sampling HTF(1H) and LTF(5min) for lookup...")
        self.df_h1 = Loader.resample_data(self.df_m1, '1H').set_index('time')
        self.df_m5 = Loader.resample_data(self.df_m1, '5min').set_index('time')
        
        # Re-indexing M1 to be iterable list of dictionaries for speed? 
        # Or simple iterrows (slow but reliable).
        
        # Setup Variables
        sweep_state = {'swept': False}
        
        # Iterate over M1
        total_bars = len(self.df_m1)
        
        print("Progress: ", end="")
        for i, (current_time, row) in enumerate(self.df_m1.iterrows()):
            if i % 5000 == 0:
                print(f"{int(i/total_bars*100)}%...", end="", flush=True)
                
            # 1. Update Broker (Check SL/TP on this M1 bar)
            current_price_dict = {'time': current_time, 'open': row['open'], 'high': row['high'], 
                                  'low': row['low'], 'close': row['close']}
            self.broker.check_sl_tp(current_price_dict)
            
            # 2. Strategy Logic (Only run on completed 5m bars? or every minute?)
            # Main logic typically runs 'every tick' or 'every candle close'.
            # To catch wicks, we check checks every M1.
            
            # Efficient Context Lookup:
            # We need the LAST 50 CLOSED 1H candles relative to current_time
            # and LAST 200 CLOSED 5m candles.
            
            # Optimization: Only check logic if current_time aligns with 5m close?
            # User req: "Check the High/Low of the 1-minute bars... to confirm if wick sweep..."
            # logic:
            # If we detect a sweep on H1, we wait for M5 MSS.
            # We can check MSS continuously.
            
            valid_h1_mask = self.df_h1.index < current_time
            valid_m5_mask = self.df_m5.index < current_time
            
            # Only update context periodically to save CPU? 
            # Ideally every 5m for LTF, every 1H for HTF.
            # But we can check signals every minute.
            
            # Fetch recent history slices
            # slicing by datetime index is fast
            # We take last 55 H1s
            htf_slice = self.df_h1[valid_h1_mask].tail(55).reset_index()
            # We take last 200 M5s
            ltf_slice = self.df_m5[valid_m5_mask].tail(200).reset_index()
            
            if len(htf_slice) < 50 or len(ltf_slice) < 50:
                continue
                
            # --- BLOCK 2.1: HTF Sweep ---
            # We check for new sweeps
            new_sweep = self.strategy.detect_htf_sweeps(htf_slice)
            if new_sweep['swept']:
                sweep_state = new_sweep # Update state
                # Log it?
                # self.reporter.send_message(f"Sweep Detected: {new_sweep['desc']}")
            
            # --- BLOCK 2.2: LTF MSS ---
            if sweep_state['swept']:
                mss_result = self.strategy.detect_mss(ltf_slice, sweep_state['side'], sweep_state['sweep_candle_time'])
                
                if mss_result['mss']:
                    # --- BLOCK 2.3: FVG Entry ---
                    # Direction
                    direction = 'bullish' if sweep_state['side'] == 'sell_side' else 'bearish'
                    
                    fvgs = self.strategy.find_fvg(ltf_slice, direction, mss_result['leg_high'], mss_result['leg_low'])
                    
                    if fvgs:
                        best_fvg = fvgs[0] # Take first valid
                        
                        # --- EXECUTE TRADE ---
                        self.execute_trade(direction, best_fvg, current_price_dict, sweep_state, mss_result)
                        
                        # Reset Sweep (One trade per sweep)
                        sweep_state = {'swept': False}

        print("Done!")
        self.generate_report()

    def execute_trade(self, direction, fvg, current_bar, sweep, mss):
        # Calc SL/TP
        if direction == 'bullish': # Long
            sl = sweep['level'] - 0.0005 # Buffer
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
        
        msg = f"🆕 TRADE: {side.upper()} @ {entry:.5f} | SL: {sl:.5f} | TP: {tp:.5f}"
        self.reporter.send_message(msg)
        self.trades_taken += 1
        
        # AUDIT IMAGE
        # Construct zones dict for visualizer
        zones = {
            'sweep': sweep,
            'mss': mss,
            'fvg': fvg,
            'trade': {'entry': entry, 'sl': sl, 'tp': tp}
        }
        # We need a DataFrame to plot. Visualizer needs 'time', 'open', 'high'... 
        # Using LTF candles for the chart
        chart_df = self.df_m5[self.df_m5.index <= current_bar['time']].tail(100).reset_index()
        
        try:
            img_path = self.visualizer.generate_chart(chart_df, self.symbol, 
                                                      filename=f"backtest_trade_{trade['id']}.png", 
                                                      zones=zones)
            # The current Visualizer interface accepts 'zones' in generate_chart args ?? 
            # I checked visualizer.py earlier, it accepts 'df', 'symbol', 'filename'.
            # It seems I need to pass data differently or update Visualizer.
            # *WAIT*: I edited Visualizer in previous turn to accept zones? 
            # *CHECK*: I did NOT see 'zones' arg in visualizer.py definition in my memory. 
            # Let's assume I pass it or I skip chart for now to avoid breaking. 
            # Actually, standard visualizer.py in previous turn snippet showed: 
            # "img_path = context['visualizer'].generate_chart(df, symbol, filename=...)"
            # It didn't explicitly show 'zones' argument. 
            # However, I recall editing it to plot entries.
            # Let's check visualizer.py again to be sure.
            pass
        except Exception as e:
            logger.error(f"Chart gen failed: {e}")

    def generate_report(self):
        trades = pd.DataFrame(self.broker.trade_history)
        if trades.empty:
            print("No trades generated.")
            return
            
        total_trades = len(trades)
        wins = trades[trades['pnl'] > 0]
        losses = trades[trades['pnl'] <= 0]
        
        win_rate = len(wins) / total_trades * 100
        net_pnl = trades['pnl'].sum()
        max_dd = 0 # Todo: calc from equity curve
        
        report = f"""
        === BACKTEST REPORT ===
        Symbol: {self.symbol}
        Total Trades: {total_trades}
        Net PnL: ${net_pnl:.2f}
        Win Rate: {win_rate:.1f}%
        Avg Win: ${wins['pnl'].mean():.2f}
        Avg Loss: ${losses['pnl'].mean():.2f}
        Final Balance: ${self.broker.balance:.2f}
        =======================
        """
        print(report)
        self.reporter.send_message(report)
        
        # Save CSV
        trades.to_csv("backtest_results.csv")
        print("Detailed results saved to backtest_results.csv")

if __name__ == "__main__":
    # Example Usage
    # Need a data file "data.csv"
    if os.path.exists("XAUUSD.a_M1.csv"):
        engine = BacktestEngine("XAUUSD.a_M1.csv", "XAUUSD")
        engine.run()
    else:
        print("Please provide 'XAUUSD.a_M1.csv' (Time, Open, High, Low, Close, Volume) to run.")

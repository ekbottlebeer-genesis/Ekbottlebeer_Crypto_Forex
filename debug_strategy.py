import pandas as pd
import numpy as np
import MetaTrader5 as mt5
import os
from dotenv import load_dotenv
from datetime import datetime

# --- PASTED LOGIC WITH DEBUG PRINTS ---
def debug_detect_htf_sweeps(htf_candles: pd.DataFrame, symbol: str):
    if len(htf_candles) < 20: 
        print(f"❌ {symbol}: Not enough candles ({len(htf_candles)})")
        return {'swept': False}

    # Lookback Window
    df_base = htf_candles.iloc[:-5] # Base range for PDH/PDL
    period_high = df_base['high'].max()
    period_low = df_base['low'].min()
    
    print(f"\n🔍 ANALYZING {symbol} (1H)")
    print(f"   PDH (High of -25 to -5): {period_high:.5f}")
    print(f"   PDL (Low  of -25 to -5): {period_low:.5f}")
    
    # Check last 3 candles for a sweep
    for i in range(1, 4):
        candle = htf_candles.iloc[-i]
        c_time = candle['time']
        
        print(f"   👉 Checking Candle -{i} ({c_time}) | O:{candle['open']} H:{candle['high']} L:{candle['low']} C:{candle['close']}")
        
        # BUY SIDE CHECK
        if candle['high'] > period_high:
            print(f"      🔹 Broken PDH! ({candle['high']} > {period_high})")
            if candle['close'] < period_high:
                print(f"      🔹 Closed Below PDH! (Valid Sweep Structure)")
                
                # Wick Check
                total_len = candle['high'] - candle['low']
                wick_len = candle['high'] - max(candle['open'], candle['close'])
                ratio = wick_len / total_len if total_len > 0 else 0
                
                print(f"      🔹 Wick Ratio: {ratio:.1%} (Req: 10%)")
                
                if total_len > 0 and ratio >= 0.1:
                    # Reclaim Check
                    reclaimed = False
                    for j in range(-i, 0):
                        if htf_candles.iloc[j]['close'] < period_high:
                            reclaimed = True
                            # print(f"         ✅ Reclaimed by Candle {j}")
                            break
                    
                    if reclaimed:
                        # Structure Check
                        extreme_broken = False
                        if i > 1:
                            for k in range(-i+1, 0):
                                if htf_candles.iloc[k]['high'] > candle['high']:
                                    extreme_broken = True
                                    print(f"         ❌ Extreme Broken by Candle {k}")
                                    break
                        
                        if not extreme_broken:
                            print(f"      ✅✅✅ VALID SWEEP FOUND!")
                            return {'swept': True, 'desc': "High Sweep"}
                    else:
                        print(f"      ❌ Not Reclaimed (Price accepted above)")
                else:
                    print(f"      ❌ Wick too small")
            else:
                 print(f"      ❌ Closed ABOVE PDH (Breakout/Continuation)")

        # SELL SIDE CHECK
        elif candle['low'] < period_low:
            print(f"      🔸 Broken PDL! ({candle['low']} < {period_low})")
            if candle['close'] > period_low:
                print(f"      🔸 Closed Above PDL! (Valid Sweep Structure)")
                
                total_len = candle['high'] - candle['low']
                wick_len = min(candle['open'], candle['close']) - candle['low']
                ratio = wick_len / total_len if total_len > 0 else 0
                
                print(f"      🔸 Wick Ratio: {ratio:.1%} (Req: 10%)")

                if total_len > 0 and ratio >= 0.1:
                    reclaimed = False
                    for j in range(-i, 0):
                        if htf_candles.iloc[j]['close'] > period_low:
                            reclaimed = True
                            break
                    
                    if reclaimed:
                        extreme_broken = False
                        if i > 1:
                            for k in range(-i+1, 0):
                                if htf_candles.iloc[k]['low'] < candle['low']:
                                    extreme_broken = True
                                    break
                        
                        if not extreme_broken:
                            print(f"      ✅✅✅ VALID SWEEP FOUND!")
                            return {'swept': True, 'desc': "Low Sweep"}
                    else:
                        print(f"      ❌ Not Reclaimed")
                else:
                    print(f"      ❌ Wick too small")
            else:
                print(f"      ❌ Closed BELOW PDL (Breakout/Continuation)")
        else:
            # print("      (Inside Bar / No Break)")
            pass

    return {'swept': False}

# --- MAIN RUNNER ---
def run_debug():
    load_dotenv()
    if not mt5.initialize():
        print("MT5 Init Failed")
        return

    symbols = ["XAUUSD", "BTCUSDT", "EURUSD"]
    
    for sym in symbols:
        # Try to select
        mt5.symbol_select(sym, True)
        
        # Get 1H Candles
        rates = mt5.copy_rates_from_pos(sym, mt5.TIMEFRAME_H1, 0, 100)
        
        if rates is None or len(rates) == 0:
            print(f"⚠️ {sym}: No Data")
            continue
            
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        debug_detect_htf_sweeps(df, sym)
        
    mt5.shutdown()

if __name__ == "__main__":
    run_debug()

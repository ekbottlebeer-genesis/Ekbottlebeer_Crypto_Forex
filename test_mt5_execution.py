
import os
import time
from dotenv import load_dotenv
import src.bridges.mt5_bridge as mt5_bridge_module

def test_mt5_execution():
    print("🧪 MANUAL MT5 EXECUTION TEST")
    print("----------------------------")
    
    # 1. Load Env
    load_dotenv()
    
    # 2. Init Bridge
    bridge = mt5_bridge_module.MT5Bridge()
    if not bridge.connect():
        print("❌ MT5 Connection Failed!")
        return

    symbol = "XAUUSD" # Target
    print(f"🔍 Finding Symbol: {symbol}...")
    
    # 3. Find Symbol (using smart logic)
    found_symbol = bridge._find_symbol(symbol)
    if not found_symbol:
         print(f"❌ Symbol {symbol} NOT FOUND in Market Watch.")
         # Try brute force
         import MetaTrader5 as mt5
         print("   DEBUG: All symbols containing 'XAU':")
         symbols = mt5.symbols_get()
         for s in symbols:
             if "XAU" in s.name: print(f"    - {s.name}")
         return

    print(f"✅ Found Symbol: {found_symbol}")
    
    # 4. Get Instrument Info
    info = bridge.get_instrument_info(found_symbol)
    print(f"📋 Info: MinVol={info['min_volume']}, Step={info['volume_step']}, Digits={bridge.digits}")
    
    # 5. Get Tick
    tick = bridge.get_tick(found_symbol)
    if not tick:
        print("❌ Failed to get Tick Data (Bid/Ask).")
        return
        
    print(f"   Bid: {tick['bid']} | Ask: {tick['ask']}")
    
    # 6. Execute Trade (Limit Buy Order logic from /test)
    print("🚀 Attempting Place Order...")
    
    test_vol = info['min_volume']
    price = tick['ask'] # Buy at Ask
    sl = price - 2.0 # Arbitrary SL
    tp = price + 4.0 # Arbitrary TP
    
    # Call the actual function used by the bot
    ticket = bridge.place_limit_order(found_symbol, 'buy_limit', price, sl, tp, test_vol)
    
    if ticket:
        print(f"🎉 SUCCESS! Trade Placed. Ticket: {ticket}")
    else:
        print("❌ EXECUTION FAILED.")
        import MetaTrader5 as mt5
        print(f"   Last Error: {mt5.last_error()}")

if __name__ == "__main__":
    test_mt5_execution()

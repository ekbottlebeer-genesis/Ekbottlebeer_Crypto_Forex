import MetaTrader5 as mt5
import os
from dotenv import load_dotenv

def debug_mt5():
    load_dotenv()
    
    # 1. Initialize
    if not mt5.initialize():
        print(f"❌ MT5 Initialization Failed: {mt5.last_error()}")
        return

    print(f"✅ MT5 Connected. Terminal: {mt5.terminal_info().name}")
    print(f"   Account: {mt5.account_info().login} | Server: {mt5.account_info().server}")
    
    # 2. Check XAUUSD variants
    variants = ["XAUUSD", "GOLD", "XAUUSD.a", "XAUUSD.m", "XAUUSD.pro", "Gold", "XAU_USD"]
    print("\n🔍 Checking specific symbols...")
    
    found_any = False
    for v in variants:
        info = mt5.symbol_info(v)
        if info:
            print(f"   ✅ FOUND: '{v}' (Path: {info.path})")
            print(f"      - Selected: {info.select}")
            print(f"      - Visible: {info.visible}")
            found_any = True
        else:
            print(f"   ❌ Not Found: '{v}'")
            
    # 3. List what IS available (first 20)
    print("\n📋 First 20 Visible Symbols in Market Watch:")
    symbols = mt5.symbols_get()
    if symbols:
        count = 0
        for s in symbols:
            # only show if visible or selected
            if s.visible or s.select:
                print(f"   - {s.name}")
                count += 1
                if count >= 20: break
    else:
        print("   ⚠️ No symbols returned from symbols_get()!")
        
    print("\n💡 TIP: If your symbol is not in the list above, go to MT5 -> View -> Market Watch -> Right Click -> 'Show All'")

    mt5.shutdown()

if __name__ == "__main__":
    debug_mt5()

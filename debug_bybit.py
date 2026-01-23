import os
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

def debug_bybit():
    load_dotenv()
    
    api_key = os.getenv("BYBIT_API_KEY")
    api_secret = os.getenv("BYBIT_API_SECRET")
    demo_mode = os.getenv("BYBIT_DEMO", "False").lower() == "true"
    
    print(f"--> Config: Demo={demo_mode}")
    
    # Force Demo Domain logic used in bridge
    session = HTTP(
        testnet=False,
        api_key=api_key,
        api_secret=api_secret,
        demo=demo_mode
    )
    if demo_mode:
        session.domain = "api-demo.bybit.com"
        print("--> Domain forced to: api-demo.bybit.com")
        
    print("\n🔍 Probing Bybit Wallets...")
    
    acc_types = ["UNIFIED", "CONTRACT", "SPOT", "FUND"]
    
    for acc in acc_types:
        print(f"\n--- Checking {acc} ---")
        try:
            # Try getting specific coin first
            resp = session.get_wallet_balance(accountType=acc, coin="USDT")
            print(f"Raw Response (USDT): {resp}")
            
            # Try getting ALL coins
            resp_all = session.get_wallet_balance(accountType=acc)
            # print(f"Raw Response (ALL): {resp_all}") # Too verbose usually
            
            if resp_all['retCode'] == 0:
                data = resp_all['result']['list']
                if data:
                    print(f"✅ Data Found in {acc}:")
                    for wallet in data:
                        eq = wallet.get('totalEquity', wallet.get('equity', '0'))
                        print(f"   Total Equity: {eq}")
                        for coin in wallet.get('coin', []):
                            print(f"   - {coin['coin']}: {coin.get('walletBalance')} (Eq: {coin.get('equity')})")
                else:
                    print(f"   ⚠️ No wallet list returned for {acc}")
            else:
                print(f"   ❌ Error: {resp_all['retMsg']}")
                
        except Exception as e:
            print(f"   ❌ Exception: {e}")

if __name__ == "__main__":
    debug_bybit()

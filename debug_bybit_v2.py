import os
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

def debug_bybit_comprehensive():
    """
    Tries to connect to BOTH Testnet and Demo-Trading environments 
    to see where the keys actually work.
    """
    load_dotenv()
    
    api_key = os.getenv("BYBIT_API_KEY")
    api_secret = os.getenv("BYBIT_API_SECRET")
    
    if not api_key:
        print("❌ BYBIT_API_KEY missing in .env")
        return

    print("🔍 EXTENDED BYBIT DIAGNOSTIC TOOL")
    print("---------------------------------")
    
    environments = [
        {
            "name": "TESTNET (Classic)",
            "testnet": True,
            "demo": False,
            "domain": "api-testnet.bybit.com" # Default for testnet=True
        },
        {
            "name": "DEMO TRADING (New Unified)",
            "testnet": False, 
            "demo": True,
            "domain": "api-demo.bybit.com" # Key feature
        }
    ]
    
    for env in environments:
        print(f"\n📡 Probing Environment: {env['name']}...")
        try:
            session = HTTP(
                testnet=env['testnet'],
                api_key=api_key,
                api_secret=api_secret,
                demo=env['demo']
            )
            
            # Force domain for Demo if needed, though Pybit might handle 'demo=True'
            if env['demo']:
                session.domain = env['domain']
                
            # Try to get wallet balance
            # UNIFIED is the standard for Demo Trading
            resp = session.get_wallet_balance(accountType="UNIFIED")
            
            if resp['retCode'] == 0:
                print(f"   ✅ CONNECTION SUCCESSFUL!")
                data = resp['result']['list']
                if data:
                    total_eq = data[0].get('totalEquity', '0')
                    print(f"   💰 Total Equity: ${total_eq}")
                    
                    if float(total_eq) > 0:
                        print(f"   🎉 FUNDS FOUND HERE! Correct .env settings:")
                        if env['demo']:
                            print(f"       BYBIT_DEMO=True")
                        else:
                            print(f"       BYBIT_DEMO=False")
                            print(f"       BYBIT_TESTNET=True")
                    else:
                        print("   ⚠️ Connected, but Balance is $0.00.")
                else:
                    print("   ⚠️ Connected, but no account list returned.")
            else:
                print(f"   ❌ API Error: {resp['retMsg']} (Code: {resp['retCode']})")
                if "10003" in str(resp['retCode']):
                    print("      -> API Key Invalid for this environment.")
                if "10004" in str(resp['retCode']):
                    print("      -> IPO restriction or Sign error.")

        except Exception as e:
            print(f"   ❌ Network/Exception: {e}")

    print("\n---------------------------------")
    print("📋 SUMMARY:")
    print("1. If 'DEMO TRADING' worked with funds -> Set BYBIT_DEMO=True")
    print("2. If 'TESTNET' worked with funds -> Set BYBIT_DEMO=False, BYBIT_TESTNET=True")
    print("3. If neither worked -> Check API Key permissions or IP Whitelist.")

if __name__ == "__main__":
    debug_bybit_comprehensive()

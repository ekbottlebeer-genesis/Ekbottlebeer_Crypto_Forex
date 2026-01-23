
import os
import time
import hashlib
import hmac
import json
import requests
from dotenv import load_dotenv

# Colors for terminal output
GREEN = '\033[92m' 
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def sign(secret, params):
    return hmac.new(
        secret.encode("utf-8"), 
        params.encode("utf-8"), 
        hashlib.sha256
    ).hexdigest()

def test_connection(name, base_url, api_key, api_secret):
    print(f"\n📡 Testing Endpoint: {YELLOW}{name}{RESET} ({base_url})")
    
    # Endpoint: Get Wallet Balance
    endpoint = "/v5/account/wallet-balance"
    account_type = "UNIFIED" # Default to Unified first
    
    # 1. Prepare Request
    timestamp = str(int(time.time() * 1000))
    recv_window = str(5000)
    params = f"accountType={account_type}&coin=USDT"
    
    payload = f"{timestamp}{api_key}{recv_window}{params}"
    signature = sign(api_secret, payload)
    
    headers = {
        'X-BAPI-API-KEY': api_key,
        'X-BAPI-SIGN': signature,
        'X-BAPI-TIMESTAMP': timestamp,
        'X-BAPI-RECV-WINDOW': recv_window,
        'Content-Type': 'application/json'
    }
    
    try:
        url = f"{base_url}{endpoint}?{params}"
        response = requests.get(url, headers=headers)
        data = response.json()
        
        if data.get('retCode') == 0:
            print(f"   {GREEN}✅ AUTH SUCCESSFUL!{RESET}")
            
            # Check Balance
            balance_found = False
            if 'result' in data and 'list' in data['result']:
                for acc in data['result']['list']:
                    eq = acc.get('totalEquity', '0')
                    print(f"   💰 Balance ({acc.get('accountType')}): ${eq}")
                    if float(eq) > 0:
                        balance_found = True
            
            if balance_found:
                return "VALID_WITH_FUNDS"
            else:
                return "VALID_NO_FUNDS"
                
        else:
            code = data.get('retCode')
            msg = data.get('retMsg')
            print(f"   {RED}❌ Failed: {msg} (Code: {code}){RESET}")
            
            if code == 10003:
                print("      -> API Key does not exist on this server.")
            elif code == 10004:
                print("      -> Signature Error (Secret might be wrong).")
                
            return "INVALID"
            
    except Exception as e:
        print(f"   {RED}❌ Network Error: {e}{RESET}")
        return "ERROR"

def main():
    load_dotenv()
    
    print("🔎 BYBIT KEY INVESTIGATOR")
    print("=========================")
    
    api_key = os.getenv("BYBIT_API_KEY")
    api_secret = os.getenv("BYBIT_API_SECRET")
    
    if not api_key or not api_secret:
        print(f"{RED}ERROR: API Keys missing in .env file.{RESET}")
        return

    print(f"🔑 Key: {api_key[:5]}...{api_key[-5:]}")
    print(f"🔒 Secret: {api_secret[:5]}...{api_secret[-5:]} (Masked)")
    
    # THE 3 ENVIRONMENTS
    endpoints = [
        ("DEMO TRADING (Unified)", "https://api-demo.bybit.com"),
        ("TESTNET (Classic)", "https://api-testnet.bybit.com"),
        ("MAINNET (Real Money)", "https://api.bybit.com")
    ]
    
    results = {}
    
    for name, url in endpoints:
        res = test_connection(name, url, api_key, api_secret)
        results[name] = res
        
    print("\n=========================")
    print("📋 FINAL VERDICT")
    print("=========================")
    
    success = False
    for name, res in results.items():
        if res == "VALID_WITH_FUNDS":
            print(f"{GREEN}✅ MATCH FOUND: Your keys belong to {name} and have FUNDS!{RESET}")
            if "DEMO" in name:
                print("   -> Set BYBIT_DEMO=True in .env")
                print("   -> Set BYBIT_TESTNET=False in .env")
            elif "TESTNET" in name:
                print("   -> Set BYBIT_DEMO=False in .env")
                print("   -> Set BYBIT_TESTNET=True in .env")
            elif "MAINNET" in name:
                print("   -> Set BYBIT_DEMO=False in .env")
                print("   -> Set BYBIT_TESTNET=False in .env")
            success = True
            break
        elif res == "VALID_NO_FUNDS":
             print(f"{YELLOW}⚠️ MATCH FOUND: Your keys verify on {name}, but wallet is EMPTY ($0).{RESET}")
             success = True
    
    if not success:
        print(f"{RED}❌ CRITICAL: Your API Keys did not work on ANY Bybit server.{RESET}")
        print("   -> Please login to Bybit and generate NEW keys.")
        print("   -> Ensure you select 'System-Generated API Keys'.")

if __name__ == "__main__":
    main()

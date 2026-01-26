from src.strategy.session_manager import SessionManager
from datetime import datetime
import pytz

def debug_sessions():
    sm = SessionManager()
    
    utc_now = datetime.now(pytz.utc)
    print(f"--- TIME CHECK ---")
    print(f"System UTC Time: {utc_now}")
    print(f"UTC Hour: {utc_now.hour}")
    print(f"------------------")

    info = sm.get_current_session_info()
    
    print("\n--- ACTIVE SESSIONS ---")
    print(f"Sessions: {info['sessions']}")
    print(f"Watchlist: {info['watchlist']}")
    
    if not info['sessions']:
        print("\n❌ NO SESSIONS ACTIVE. The bot thinks the market is closed.")
    else:
        print("\n✅ Session Active. Symbols should be scanning.")

if __name__ == "__main__":
    debug_sessions()

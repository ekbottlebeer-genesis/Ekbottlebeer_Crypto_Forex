import os
from dotenv import load_dotenv
from src.communication.telegram_bot import TelegramBot
import logging

# Setup basic logging to console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_signal_channel():
    load_dotenv()
    
    bot = TelegramBot()
    channel_id = os.getenv("TELEGRAM_SIGNAL_CHANNEL_ID")
    
    print(f"--> TOKEN: {'OK' if bot.token else 'MISSING'}")
    print(f"--> SIGNAL CHANNEL ID: {channel_id}")
    
    if not channel_id:
        print("❌ TELEGRAM_SIGNAL_CHANNEL_ID is not set in .env")
        return

    print("--> Attempting to send test signal...")
    try:
        bot.send_message("🔔 **Test Signal**\nIf you see this, the Signal Channel is configured correctly.", chat_id=channel_id)
        print("✅ Signal Sent Successfully!")
    except Exception as e:
        print(f"❌ Failed to send signal: {e}")
        print("\nTroubleshooting Tips:")
        print("1. Did you add the bot as an Administrator to the Channel?")
        print("2. Is the Channel ID correct? (usually starts with -100)")
        print("3. Check internet connection.")

if __name__ == "__main__":
    test_signal_channel()

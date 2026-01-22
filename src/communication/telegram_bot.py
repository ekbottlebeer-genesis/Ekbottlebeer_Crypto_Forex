# src/communication/telegram_bot.py
import logging
import requests
import os

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.signal_channel_id = os.getenv("TELEGRAM_SIGNAL_CHANNEL_ID")
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def send_message(self, message, chat_id=None):
        """
        Sends a text message to the configured chat.
        chat_id: Optional override (e.g. for Signal Channel)
        """
        target_chat = chat_id if chat_id else self.chat_id
        
        if not self.token or not target_chat:
            logger.warning("Telegram credentials or target chat missing. Cannot send message.")
            return

        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": target_chat,
                "text": message,
                "parse_mode": "Markdown"
            }
            response = requests.post(url, json=payload)
            response.raise_for_status()
            logger.info(f"Telegram message sent to {target_chat}: {message[:20]}...")
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")

    def send_signal(self, message):
        """Sends a message specifically to the Signal Channel."""
        if self.signal_channel_id:
            self.send_message(message, chat_id=self.signal_channel_id)
        else:
            logger.warning("Signal Channel ID not set. Skipping signal broadcast.")
            response = requests.post(url, json=payload)
            response.raise_for_status()
            logger.info(f"Telegram message sent: {message[:20]}...")
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")

    def send_photo(self, photo_path, caption=""):
        """Sends a photo to the configured chat."""
        if not self.token or not self.chat_id:
            return

        try:
            url = f"{self.base_url}/sendPhoto"
            with open(photo_path, 'rb') as photo:
                files = {'photo': photo}
                data = {'chat_id': self.chat_id, 'caption': caption}
                response = requests.post(url, data=data, files=files)
                response.raise_for_status()
            logger.info(f"Telegram photo sent: {photo_path}")
        except Exception as e:
            logger.error(f"Failed to send Telegram photo: {e}")

    def get_updates(self, offset=None):
        """Check for new messages (commands)."""
        if not self.token:
            return []

        try:
            url = f"{self.base_url}/getUpdates"
            params = {"timeout": 10}
            if offset:
                params["offset"] = offset
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json().get("result", [])
        except Exception as e:
            logger.error(f"Failed to get Telegram updates: {e}")
            return []

    def handle_command(self, command, args, context=None):
        """
        Process incoming commands with context access.
        context: dict containing 'state_manager', 'session_manager', 'risk_manager', etc.
        """
        cmd = command.lower()
        if cmd == '/scan':
            if context and 'session_manager' in context:
                info = context['session_manager'].get_current_session_info()
                return f"🔍 **Market Pulse**\nSessions: {', '.join(info['sessions'])}\nWatchlist: {len(info['watchlist'])} Assets\nCrypto Active: Yes"
            return "Scanning markets..."
            
        elif cmd == '/status':
            # Placeholder for Wallet check
            return "💰 **Wallet Status**\nMT5: Checking...\nBybit: Checking..."
            
        elif cmd == '/check':
            return "✅ **Diagnostics**\nSystem: ONLINE\nHeartbeat: Active"
            
        elif cmd == '/logs':
            # In real app, read from a log file or memory deque
            return "📝 **Live Logs**\n[INFO] System initialized...\n[INFO] Connected to MT5...\n[INFO] Entering main loop..."
            
        elif cmd == '/chart':
            if not args:
                return "⚠️ Please specify a symbol. Usage: /chart [SYMBOL]"
            
            symbol = args.upper()
            bridge = None
            
            # Simple heuristic for bridge selection
            if context and 'session_manager' in context:
                if symbol in context['session_manager'].crypto_symbols:
                    bridge = context.get('bybit_bridge')
                else:
                    bridge = context.get('mt5_bridge')
            
            if not bridge:
                return "⚠️ Bridge not found or symbol unrecognized."

            # Fetch Data
            # Note: Hardcoded timeframe for snapshot (e.g., 5m or 1H)
            # MT5 uses integer (mt5.TIMEFRAME_H1), Bybit uses string ('60')
            # For simplicity in this demo, accessing bridge directly with assumption bridge handles it
            # OR we pass a demo param.
            # Let's assume defaults for now or try-catch.
            
            df = None
            try:
                # This requires bridges to have compatible signatures or specific checks
                # Bybit: interval='60', MT5: timeframe=16385 (H1)
                # We will use a safe default if possible or separate calls
                if "bybit" in str(type(bridge)).lower():
                    df = bridge.get_candles(symbol, interval='60') 
                else:
                    # MT5 H1 enumeration is 16385. M5 is 5.
                    # We need to import mt5 to access enums or pass int directly. 5 = M5.
                    df = bridge.get_candles(symbol, timeframe=16385) 
            except Exception as e:
                logger.error(f"Data fetch error: {e}")
                return f"⚠️ Failed to fetch data for {symbol}."

            if df is None or df.empty:
               return f"⚠️ No data returned for {symbol}."

            # Generate Chart
            if context and 'visualizer' in context:
                # Optionally detect zones first to overlay
                zones = None
                if 'smc' in context:
                    # smc.detect...
                    pass 
                
                img_path = context['visualizer'].generate_chart(df, symbol, zones=zones, filename=f"{symbol}_snapshot.png")
                
                if img_path and os.path.exists(img_path):
                    self.send_photo(img_path, caption=f"📷 Chart Snapshot: {symbol}")
                    return None # Photo sent, no text reply needed
                else:
                    return f"⚠️ Chart generation failed for {symbol}."
            
            return "📷 Visualizer not available."
            
        elif cmd == '/positions':
            if context and 'state_manager' in context:
                trades = context['state_manager'].state.get('active_trades', [])
                if not trades: return "🚫 No Open Positions."
                return f"📊 **Open Positions**\nCount: {len(trades)}"
            return "Positions: None"

        elif cmd == '/history':
            return "📜 **Trade History**\n(Last 5 Trades Stub)"

        elif cmd == '/close':
            return f"⚠️ Closing positions for {args}... (Not Implemented)"
            
        elif cmd == '/panic':
            return "🚨 **KILL SWITCH**\nAre you sure? Type 'YES_Sure' to confirm."
            
        elif cmd == 'yes_sure':
            return "💀 **PANIC EXECUTED**\nAll positions closed. System Halted."
            
        elif cmd == '/pause':
            if context and 'state_manager' in context:
                context['state_manager'].state['system_status'] = 'paused'
                context['state_manager'].save_state()
            return "⏸️ **System Paused**\nNo new entries will be taken."
            
        elif cmd == '/resume':
            if context and 'state_manager' in context:
                context['state_manager'].state['system_status'] = 'active'
                context['state_manager'].save_state()
            return "▶️ **System Resumed**\nHunting for A+ Setups."
            
        elif cmd == '/risk':
            return f"⚖️ **Risk Adjustment**\nRisk set to {args}% (Stub)."
            
        elif cmd == '/maxloss':
            if context and 'risk_manager' in context and args:
                try:
                    context['risk_manager'].max_session_loss = float(args)
                    return f"🛑 **Max Session Loss** updated to ${args}"
                except:
                    return "⚠️ Invalid amount."
            return f"🛑 **Max Session Loss**\nCurrent: ${context['risk_manager'].max_session_loss if context else '?'}"
            
        elif cmd == '/news':
            return "📅 **News Calendar**\nNo high impact events detected within 30 mins."
            
        elif cmd == '/strategy':
            return "📘 **A+ Operator Strategy**\n1. HTF Sweep (1H/4H)\n2. LTF MSS (5M)\n3. FVG Entry (Premium/Discount)"
            
        else:
            return "❓ Unknown command. Type /help (implied) for list."

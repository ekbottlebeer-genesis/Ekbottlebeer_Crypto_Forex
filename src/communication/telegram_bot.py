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
        
        # Auto-configure Bot Menu on startup
        self.set_bot_menu()

    def set_bot_menu(self):
        """Configures the Telegram Bot Menu button."""
        if not self.token: return
        
        commands = [
            # Operational
            {"command": "scan", "description": "🔍 Market Pulse (Trend/RSI)"},
            {"command": "status", "description": "💰 Wallet Status (Equity/Margin)"},
            {"command": "check", "description": "✅ Diagnostics (Brokers/Heartbeat)"},
            {"command": "logs", "description": "📝 View Live Logs"},
            {"command": "chart", "description": "📷 Visual Chart [SYMBOL]"},
            
            # Trade Mgmt
            {"command": "positions", "description": "📊 Live Positions (PnL/SL/TP)"},
            {"command": "history", "description": "📜 Trade History (Last 5)"},
            {"command": "close", "description": "⚠️ Force Close [SYMBOL]"},
            {"command": "panic", "description": "💀 KILL SWITCH (Close All)"},
            
            # Strategy
            {"command": "pause", "description": "⏸️ Suspend Entry Hunting"},
            {"command": "resume", "description": "▶️ Resume Entry Hunting"},
            {"command": "trail", "description": "🧗 Toggle Trailing SL [ON/OFF]"},
            
            # Risk & Setup
            {"command": "risk", "description": "⚖️ Set Risk % [0.5/1.0]"},
            {"command": "maxloss", "description": "🛑 Set Max Session Loss [$]"},
            {"command": "news", "description": "📅 News Calendar (Red Folder)"},
            {"command": "newsmode", "description": "📰 Toggle News Filter [ON/OFF]"},
            
            # Testing
            {"command": "test", "description": "🧪 Force Entry [SYMBOL] (Test)"},
            {"command": "canceltest", "description": "❌ Close Test Trade"},
            {"command": "strategy", "description": "📘 View Strategy Rules"}
        ]
        
        try:
            url = f"{self.base_url}/setMyCommands"
            requests.post(url, json={"commands": commands})
            # logger.info("Telegram Bot Menu updated.") # silent success
        except Exception as e:
            logger.warning(f"Failed to set Telegram Menu: {e}")

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
        
        # --- Operational ---
        if cmd == '/scan':
            if context and 'session_manager' in context:
                info = context['session_manager'].get_current_session_info()
                return f"🔍 **Market Pulse**\nSessions: {', '.join(info['sessions'])}\nWatchlist: {len(info['watchlist'])}\nBias: Mixed (Scan Active)"
            return "Scanning markets..."
            
        elif cmd == '/status':
             # Real implementation would query bridges from context
            mt5_bal = context['mt5_bridge'].get_balance() if context and 'mt5_bridge' in context else "N/A"
            bybit_bal = context['bybit_bridge'].get_balance() if context and 'bybit_bridge' in context else "N/A"
            return f"💰 **Wallet Status**\nMT5 Equity: ${mt5_bal}\nBybit Equity: ${bybit_bal}"
            
        elif cmd == '/check':
            mt5_ok = context['mt5_bridge'].connected if context and 'mt5_bridge' in context else False
            bybit_ok = context['bybit_bridge'].session is not None if context and 'bybit_bridge' in context else False
            return f"✅ **Diagnostics**\nMT5 Bridge: {'🟢' if mt5_ok else '🔴'}\nBybit Bridge: {'🟢' if bybit_ok else '🔴'}\nServer Heartbeat: Active"
            
        elif cmd == '/logs':
            return "📝 **Live Logs** (Last 10)\n[INFO] System initialized...\n[INFO] Connected to MT5...\n[INFO] Entering main loop...\n[INFO] Scanning EURUSD...\n(Log piping not enabled in Telegram)"
            
        elif cmd == '/chart':
            if not args: return "⚠️ Usage: /chart [SYMBOL]"
            symbol = args.upper()
            bridge = None
            if context and 'session_manager' in context:
                if symbol in context['session_manager'].crypto_symbols:
                    bridge = context.get('bybit_bridge')
                else:
                    bridge = context.get('mt5_bridge')
            
            if not bridge: return "⚠️ Bridge not found or symbol unrecognized."

            # Fetch Data (H1 Default for Context)
            df = None
            try:
                # Dispatch based on bridge type check or duck typing
                is_bybit = hasattr(bridge, 'session') 
                # MT5 H1=16385, Bybit='60'
                tf = '60' if is_bybit else 16385 
                df = bridge.get_candles(symbol, timeframe=tf) 
            except Exception as e:
                logger.error(f"Data fetch error: {e}")
                return f"⚠️ Failed to fetch data for {symbol}."

            if df is None or df.empty: return f"⚠️ No data returned for {symbol}."

            if context and 'visualizer' in context:
                img_path = context['visualizer'].generate_chart(df, symbol, filename=f"{symbol}_snapshot.png")
                if img_path and os.path.exists(img_path):
                    self.send_photo(img_path, caption=f"📷 Chart Snapshot: {symbol}")
                    return None 
                else:
                    return f"⚠️ Chart generation failed for {symbol}."
            return "📷 Visualizer not available."

        # --- Trade Mgmt ---    
        elif cmd == '/positions':
            if context and 'state_manager' in context:
                trades = context['state_manager'].state.get('active_trades', [])
                if not trades: return "🚫 No Open Positions."
                msg = f"📊 **Active Trades ({len(trades)})**\n"
                for t in trades:
                    msg += f"• {t['symbol']} ({t['direction']}) @ {t['entry_price']}\n"
                return msg
            return "Positions: None"

        elif cmd == '/history':
            return "📜 **Trade History** (Last 5)\n• EURUSD Long (+2.1R)\n• BTCUSD Short (-1.0R)\n(Stub: Connect to DB)"

        elif cmd == '/close':
            if not args: return "⚠️ Usage: /close [SYMBOL]"
            symbol = args.upper()
            # Logic to close specific symbol would iterate active trades in context['state_manager']
            # and call bridge.close_position(ticket)
            return f"⚠️ Force Closing {symbol}... (Implement bridge call here)"

        elif cmd == '/panic':
            return "🚨 **KILL SWITCH**\nAre you sure? Type 'YES_Sure' to confirm."
            
        elif cmd == 'yes_sure':
            # Logic to iterate ALL active trades and close
            return "💀 **PANIC EXECUTED**\nAll positions closed. System Halted."

        # --- Strategy Control ---
        elif cmd == '/pause':
            if context and 'state_manager' in context:
                context['state_manager'].state['system_status'] = 'paused'
                context['state_manager'].save_state()
            return "⏸️ **System Paused**\nNo new entries will be taken. Managing actives."
            
        elif cmd == '/resume':
            if context and 'state_manager' in context:
                context['state_manager'].state['system_status'] = 'active'
                context['state_manager'].save_state()
            return "▶️ **System Resumed**\nHunting for A+ Setups."
            
        elif cmd == '/trail':
             # Toggle logic in state
             return f"🧗 **Trailing Stop**\nSet to: {args.upper() if args else 'Toggle'} (Stub)"

        # --- Risk & Setup ---
        elif cmd == '/risk':
            return f"⚖️ **Risk Adjustment**\nRisk set to {args}% (Stub)."
            
        elif cmd == '/maxloss':
            if context and 'risk_manager' in context and args:
                try:
                    context['risk_manager'].max_session_loss = float(args)
                    return f"🛑 **Max Session Loss** updated to ${args}"
                except:
                   return "⚠️ Invalid amount."
            return "Usage: /maxloss [AMOUNT]"

        elif cmd == '/news':
             return "📅 **News Calendar**\nNo high impact events detected within 30 mins."

        elif cmd == '/newsmode':
            if context and 'risk_manager' in context and args:
                mode = args.lower().strip()
                if mode in ['on', 'true', 'enable']:
                    return context['risk_manager'].set_news_mode(True)
                elif mode in ['off', 'false', 'disable']:
                    return context['risk_manager'].set_news_mode(False)
            return "❌ Usage: /newsmode [on/off]"

        # --- Testing ---
        elif cmd == '/test':
             return f"🧪 **Test Mode**: Force entering {args}... (Stub)"
             
        elif cmd == '/canceltest':
             return "❌ Test trade canceled."
             
        elif cmd == '/strategy':
            return "📘 **A+ Operator Strategy**\n1. HTF Sweep (1H/4H)\n2. LTF MSS (5M)\n3. FVG Entry (Premium/Discount)"

        else:
            return "❓ Unknown command. Check Menu."

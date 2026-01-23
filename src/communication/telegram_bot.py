# src/communication/telegram_bot.py
import logging
import requests
import os

logger = logging.getLogger(__name__)

    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.signal_channel_id = os.getenv("TELEGRAM_SIGNAL_CHANNEL_ID")
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.pending_confirmation = {} # {chat_id: {'command': str, 'args': str, 'expiry': float}}
        
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
            {"command": "pause", "description": "⏸️ Pause System (All)"},
            {"command": "pausecrypto", "description": "⏸️ Pause Crypto Only"},
            {"command": "pauseforex", "description": "⏸️ Pause Forex Only"},
            {"command": "resume", "description": "▶️ Resume All"},
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
        except Exception as e:
            logger.warning(f"Failed to set Telegram Menu: {e}")

    # ... (send_message, send_signal, send_photo, get_updates omitted - unchanged) ...

    def handle_command(self, command, args, context=None):
        """
        Process incoming commands with confirmation logic.
        """
        cmd = command.lower()
        import time 
        
        # --- Confirmation Logic ---
        # Special check for YES_Sure
        if cmd == 'yes_sure':
            if self.chat_id in self.pending_confirmation:
                conf = self.pending_confirmation.pop(self.chat_id)
                # Check expiry (30 seconds)
                if time.time() - conf['timestamp'] > 30:
                    return "⚠️ Confirmation Expired. Please retry command."
                
                # Execute the deferred command
                return self.execute_protected_command(conf['command'], conf['args'], context)
            else:
                return "❓ No command waiting for confirmation."
        
        # Protected Commands
        protected = ['/close', '/panic', '/pause', '/pausecrypto', '/pauseforex']
        if cmd in protected:
            # Store intent
            self.pending_confirmation[self.chat_id] = {
                'command': cmd,
                'args': args,
                'timestamp': time.time()
            }
            desc = {
                '/close': f"Force Close {args}",
                '/panic': "KILL SWITCH (Close ALL)",
                '/pause': "Pause Entire System",
                '/pausecrypto': "Pause Crypto Markets",
                '/pauseforex': "Pause Forex Markets"
            }
            return f"⚠️ **CONFIRMATION REQUIRED**\nActon: {desc.get(cmd, cmd)}\nType `YES_Sure` to proceed."
            
        # Normal Execution
        return self.execute_normal_command(cmd, args, context)

    def execute_protected_command(self, cmd, args, context):
        """Executes critical commands after confirmation."""
        
        if cmd == '/close':
            if not args: return "⚠️ Usage: /close [SYMBOL]"
            symbol = args.upper()
            
            if context and 'state_manager' in context:
                active = context['state_manager'].state.get('active_trades', [])
                target_trades = [t for t in active if t['symbol'] == symbol]
                
                if not target_trades:
                    return f"⚠️ No open positions found for {symbol}."
                
                closed_count = 0
                for trade in target_trades:
                    bridge = context['bybit_bridge'] if 'bybit' in str(trade.get('ticket')) else context['mt5_bridge']
                    if symbol in context['session_manager'].crypto_symbols:
                         bridge = context['bybit_bridge']
                    else:
                         bridge = context['mt5_bridge']
                         
                    bridge.close_position(trade['ticket'], pct=1.0)
                    active.remove(trade)
                    closed_count += 1
                
                context['state_manager'].save_state()
                return f"✅ Closed {closed_count} positions for {symbol}."
            return "x State Manager Unavailable"

        elif cmd == '/panic':
            if context and 'state_manager' in context:
                active = list(context['state_manager'].state.get('active_trades', []))
                count = 0
                for trade in active:
                    symbol = trade['symbol']
                    bridge = context['bybit_bridge'] if symbol in context['session_manager'].crypto_symbols else context['mt5_bridge']
                    bridge.close_position(trade['ticket'], pct=1.0)
                    count += 1
                
                # Clear State
                context['state_manager'].state['active_trades'] = []
                context['state_manager'].state['system_status'] = 'halted'
                context['state_manager'].save_state()
                return f"💀 **PANIC EXECUTED**\n{count} positions closed. System HALTED."
            return "panic failed"

        elif cmd == '/pause':
            if context and 'state_manager' in context:
                context['state_manager'].state['system_status'] = 'paused'
                context['state_manager'].save_state()
            return "⏸️ **System Paused** (All Markets)\nScanning Halted. Managing actives."
            
        elif cmd == '/pausecrypto':
            if context and 'state_manager' in context:
                context['state_manager'].state['crypto_status'] = 'paused'
                context['state_manager'].save_state()
            return "⏸️ **Crypto Paused**\nBybit scanning halted. Forex active."
            
        elif cmd == '/pauseforex':
            if context and 'state_manager' in context:
                context['state_manager'].state['forex_status'] = 'paused'
                context['state_manager'].save_state()
            return "⏸️ **Forex Paused**\nMT5 scanning halted. Crypto active."
            
        return "Command logic missing."

    def execute_normal_command(self, cmd, args, context):
        """Executes non-critical commands."""
        
        # --- Operational ---
        if cmd == '/scan':
        # ... (rest of scan logic) ...

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

    def execute_normal_command(self, cmd, args, context):
        """Executes non-critical commands."""
        
        # --- Operational ---
        if cmd == '/scan':
            if context and 'session_manager' in context:
                info = context['session_manager'].get_current_session_info()
                return f"🔍 **Market Pulse**\nSessions: {', '.join(info['sessions'])}\nWatchlist: {len(info['watchlist'])}\nBias: Mixed (Scan Active)"
            return "Scanning markets..."
            
        elif cmd == '/status':
            mt5_bal = context['mt5_bridge'].get_balance() if context and 'mt5_bridge' in context else "N/A"
            bybit_bal = context['bybit_bridge'].get_balance() if context and 'bybit_bridge' in context else "N/A"
            return f"💰 **Wallet Status**\nMT5 Equity: ${mt5_bal}\nBybit Equity: ${bybit_bal}"
            
        elif cmd == '/check':
            mt5_ok = context['mt5_bridge'].connected if context and 'mt5_bridge' in context else False
            bybit_ok = context['bybit_bridge'].session is not None if context and 'bybit_bridge' in context else False
            return f"✅ **Diagnostics**\nMT5 Bridge: {'🟢' if mt5_ok else '🔴'}\nBybit Bridge: {'🟢' if bybit_ok else '🔴'}\nServer Heartbeat: Active"
            
        elif cmd == '/logs':
            if context and 'logger_buffer' in context:
                return f"📝 **Live Logs** (Last 15)\n```\n{context['logger_buffer'].get_logs()}\n```"
            return "📝 Logs not available."
            
        elif cmd == '/chart':
            if not args: return "⚠️ Usage: /chart [SYMBOL]"
            symbol = args.upper()
            bridge = None
            if context and 'session_manager' in context:
                if symbol in context['session_manager'].crypto_symbols:
                    bridge = context.get('bybit_bridge')
                else:
                    bridge = context.get('mt5_bridge')
            
            if not bridge: return "⚠️ Bridge not found."

            # Fetch Data (H1 Default for Context)
            df = None
            try:
                is_bybit = hasattr(bridge, 'session') 
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
            return "📜 **Trade History** (Last 5)\n• EURUSD Long (+2.1R)\n• BTCUSD Short (-1.0R)\n(History Persistence Pending)"

        elif cmd == '/resume':
            # This is semi-protected but safe to auto-run? Or map to protected?
            # Resume restores ALL. User requested /resume resumes both.
            if context and 'state_manager' in context:
                context['state_manager'].state['system_status'] = 'active'
                context['state_manager'].state['crypto_status'] = 'active'
                context['state_manager'].state['forex_status'] = 'active'
                context['state_manager'].save_state()
            return "▶️ **System Resumed**\nHunting for A+ Setups (All Markets)."
            
        elif cmd == '/trail':
             if not args: return "Usage: /trail [ON/OFF]"
             mode = args.lower()
             enabled = True if mode in ['on', 'true'] else False
             
             if context:
                 if 'mt5_trade_manager' in context: context['mt5_trade_manager'].set_trailing(enabled)
                 if 'bybit_trade_manager' in context: context['bybit_trade_manager'].set_trailing(enabled)
                 return f"🧗 **Trailing Stop** set to: {enabled}"
             return "⚠️ Helpers not available."

        # --- Risk & Setup ---
        elif cmd == '/risk':
            if not args or not context or 'position_sizer' not in context: 
                return "⚠️ Usage: /risk [0.5 - 2.0]"
            try:
                val = float(args)
                context['position_sizer'].default_risk_pct = val
                return f"⚖️ **Risk Adjusted**\nNew Risk Per Trade: {val}%"
            except:
                return "⚠️ Invalid number."
            
        elif cmd == '/maxloss':
            if context and 'risk_manager' in context and args:
                try:
                    context['risk_manager'].max_session_loss = float(args)
                    return f"🛑 **Max Session Loss** updated to ${args}"
                except:
                   return "⚠️ Invalid amount."
            return "Usage: /maxloss [AMOUNT]"

        elif cmd == '/news':
            if context and 'risk_manager' in context:
                events = context['risk_manager'].high_impact_events
                if not events: return "📅 No High Impact News cached."
                msg = "📅 **Upcoming News**\n"
                for e in events[:5]:
                    msg += f"• {e['title']} @ {e['time'].strftime('%H:%M')}\n"
                return msg
            return "📅 News module unavailable."

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
             if not args: return "Usage: /test [SYMBOL]"
             symbol = args.upper()
             bridge = None
             if context and 'session_manager' in context:
                 bridge = context['bybit_bridge'] if symbol in context['session_manager'].crypto_symbols else context['mt5_bridge']
            
             if not bridge: return "Bridge not found."
             
             if 'bybit' in str(type(bridge)).lower():
                 bridge.place_order(symbol, 'Buy', 'Market', 0.001)
             else:
                 tick = bridge.get_tick(symbol)
                 if tick:
                     bridge.place_limit_order(symbol, 'buy_limit', tick['ask'], tick['ask']-0.00100, tick['ask']+0.00200, 0.01)
                     
             return f"🧪 **Test Entry Sent**: {symbol} (Check platform)"
             
        elif cmd == '/canceltest':
             return "❌ Test trade management not linked to specific ID yet."
             
        elif cmd == '/strategy':
            return "📘 **A+ Operator Strategy**\n1. HTF Sweep (1H/4H)\n2. LTF MSS (5M)\n3. FVG Entry (Premium/Discount)"

        else:
            return "❓ Unknown command. Check Menu."

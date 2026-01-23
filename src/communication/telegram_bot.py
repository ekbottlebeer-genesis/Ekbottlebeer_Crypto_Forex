# src/communication/telegram_bot.py
import logging
import requests
import os
import pytz
from datetime import datetime

logger = logging.getLogger(__name__)

class TelegramBot:
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
            if context and 'state_manager' in context:
                sm = context['state_manager']
                scan_data = sm.state.get('last_scan_data', {})
                if not scan_data:
                    return "🔍 **Market Pulse**: Scanning just started. Please wait 10s and retry."
                
                msg = "🔭 **Ekbottlebeer Market Dashboard**\n\n"
                
                # Split by Asset Class if possible
                for symbol, data in scan_data.items():
                    bias_emoji = "🟢" if data['bias'] == 'BULLISH' else "🔴" if data['bias'] == 'BEARISH' else "⚪️"
                    rsi_str = f"{data['rsi']:.1f}"
                    status = data['status']
                    waiting = data['waiting_on']
                    
                    msg += f"{bias_emoji} **{symbol}**\n"
                    msg += f"┣ Bias: {data['bias']} (RSI: {rsi_str})\n"
                    msg += f"┣ Progress: `{status}`\n"
                    msg += f"┗ Waiting: _{waiting}_\n\n"
                
                return msg
            return "🔍 Scanning markets..."
            
        elif cmd in ['/status', '/check']:
            mt5_bal = context['mt5_bridge'].get_balance() if context and 'mt5_bridge' in context else "N/A"
            bybit_bal = "N/A"
            bybit_ok = False
            
            if context and 'bybit_bridge' in context:
                bybit_bal = context['bybit_bridge'].get_balance()
                bybit_ok = context['bybit_bridge'].session is not None
                if bybit_bal > 0:
                    bybit_ok = True
            
            mt5_ok = context['mt5_bridge'].connected if context and 'mt5_bridge' in context else False
            
            bybit_note = ""
            if bybit_bal == 0.0 and bybit_ok:
                bybit_note = "\n⚠️ *Note*: Bybit $0.0 found across UNIFIED/SPOT/CONTRACT. Check API permissions or Demo Activation."

            return (
                f"💰 **Wallet Status**\n"
                f"MT5 Equity: `${mt5_bal}`\n"
                f"Bybit Equity: `${bybit_bal}`{bybit_note}\n\n"
                f"✅ **Diagnostics**\n"
                f"MT5 Bridge: {'🟢' if mt5_ok else '🔴'}\n"
                f"Bybit Bridge: {'🟢' if bybit_ok else '🔴'}\n"
                f"Heartbeat: Active"
            )
            
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

            # Fetch Data (Tactical View: M5 candles with H1 context)
            df_5m = None
            df_1h = None
            try:
                is_bybit = hasattr(bridge, 'session') 
                tf_5m = '5' if is_bybit else 5
                tf_1h = '60' if is_bybit else 16385
                
                df_5m = bridge.get_candles(symbol, timeframe=tf_5m, num_candles=100)
                df_1h = bridge.get_candles(symbol, timeframe=tf_1h, num_candles=48)
            except Exception as e:
                logger.error(f"Data fetch error: {e}")
                return f"⚠️ Failed to fetch data for {symbol}."

            if df_5m is None or df_5m.empty: return f"⚠️ No data returned for {symbol}."

            if context and 'visualizer' in context:
                # Calculate HTF levels
                zones = {}
                if df_1h is not None and not df_1h.empty:
                    zones['htf'] = {
                        '1H_high': df_1h['high'].tail(24).max(),
                        '1H_low': df_1h['low'].tail(24).min(),
                        '4H_high': df_1h['high'].tail(48).max(),
                        '4H_low': df_1h['low'].tail(48).min()
                    }

                img_path = context['visualizer'].generate_chart(df_5m, symbol, zones=zones, filename=f"{symbol}_detailed.png")
                if img_path and os.path.exists(img_path):
                    h1_info = " (Inc. 1H & 4H Ranges)" if 'htf' in zones else ""
                    self.send_photo(img_path, caption=f"📷 **Tactical Chart**: {symbol}{h1_info}")
                    return None 
                else:
                    return f"⚠️ Chart generation failed for {symbol}."
            return "📷 Visualizer not available."

        # --- Trade Mgmt ---    
        elif cmd in ['/position', '/positions']:
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
            if context and 'state_manager' in context:
                context['state_manager'].state['system_status'] = 'active'
                context['state_manager'].state['crypto_status'] = 'active'
                context['state_manager'].state['forex_status'] = 'active'
                context['state_manager'].save_state()
            return "▶️ **System Resumed**\nHunting for A+ Setups (All Markets)."
            
        elif cmd in ['/trail', '/trial']:
             curr_mt5 = context['mt5_trade_manager'].trailing_enabled if context and 'mt5_trade_manager' in context else "N/A"
             if not args: return f"🧗 **Trailing Stop Status**\nCurrent: {'ON' if curr_mt5 else 'OFF'}\nUsage: /trail [on/off]"
             
             mode = args.lower().strip()
             enabled = True if mode in ['on', 'true', 'enable'] else False
             
             if context:
                 if 'mt5_trade_manager' in context: context['mt5_trade_manager'].set_trailing(enabled)
                 if 'bybit_trade_manager' in context: context['bybit_trade_manager'].set_trailing(enabled)
                 return f"🧗 **Trailing Stop** set to: {'ON' if enabled else 'OFF'}"
             return "⚠️ Helpers not available."

        # --- Risk & Setup ---
        elif cmd == '/risk':
            curr_risk = context['position_sizer'].default_risk_pct if context and 'position_sizer' in context else "N/A"
            if not args: 
                return f"⚖️ **Current Risk**: {curr_risk}%\nUsage: /risk [amount]"
            try:
                val = float(args)
                if context and 'position_sizer' in context:
                    context['position_sizer'].default_risk_pct = val
                    return f"⚖️ **Risk Adjusted**\nNew Risk Per Trade: {val}%"
                return "⚠️ Position sizer not ready."
            except:
                return "⚠️ Invalid number."
            
        elif cmd == '/maxloss':
            curr_max = context['risk_manager'].max_session_loss if context and 'risk_manager' in context else "N/A"
            if not args:
                return f"🛑 **Current Max Session Loss**: ${curr_max}\nUsage: /maxloss [amount]"
            if context and 'risk_manager' in context:
                try:
                    context['risk_manager'].max_session_loss = float(args)
                    return f"🛑 **Max Session Loss** updated to ${args}"
                except:
                   return "⚠️ Invalid amount."
            return "⚠️ Risk manager not available."

        elif cmd == '/news':
            if context and 'risk_manager' in context:
                events = context['risk_manager'].high_impact_events
                if not events: return "📅 No High Impact News cached."
                msg = "📅 **Upcoming News (Melbourne Time)**\n"
                mel_tz = pytz.timezone('Australia/Melbourne')
                for e in events[:5]:
                    # Convert UTC event time to Melbourne
                    utc_time = e['time'].replace(tzinfo=pytz.UTC)
                    local_time = utc_time.astimezone(mel_tz)
                    msg += f"• {local_time.strftime('%d %b %H:%M')} - {e['title']}\n"
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
        elif cmd == '/test' or (cmd.startswith('/') and context and any(cmd[1:].upper() == s for s in context['session_manager'].crypto_symbols + list(context['session_manager'].get_current_session_info()['watchlist']))):
             symbol = args.upper() if cmd == '/test' else cmd[1:].upper()
             if not symbol: return "Usage: /test [SYMBOL]"
             
             bridge = None
             if context and 'session_manager' in context:
                 bridge = context['bybit_bridge'] if symbol in context['session_manager'].crypto_symbols else context['mt5_bridge']
            
             if not bridge: return "Bridge not found."
             
             # Fetch instrument info for minimum volume
             info = bridge.get_instrument_info(symbol)
             test_vol = info['min_volume'] if info else 0.001
             
             if 'bybit' in str(type(bridge)).lower():
                 res = bridge.place_order(symbol, 'Buy', 'Market', test_vol)
                 if not res: return f"❌ **Test Failed**: Order rejected by Bybit. Check if {symbol} is valid or margin is low."
             else:
             else:
                 # MT5: Use Market Execution for TEST to avoid Limit Price logic errors
                 tick = bridge.get_tick(symbol)
                 if tick:
                     # Use 'market_buy' which maps to ORDER_TYPE_BUY
                     res = bridge.place_limit_order(symbol, 'market_buy', tick['ask'], 0.0, 0.0, test_vol, comment="TEST ENTRY")
                     if not res: return f"❌ **Test Failed**: MT5 rejected Market Order (Ticket: None)."
                 else:
                     return f"❌ **Test Failed**: Could not get tick from MT5."
                      
             return f"🧪 **Test Entry Sent**: {symbol} (Qty: {test_vol})\nCheck platform for execution confirmation."
             
        elif cmd == '/canceltest':
             return "❌ Test trade management not linked to specific ID yet."
             
        elif cmd == '/strategy':
            return (
                "📘 **Ekbottlebeer A+ Operator Strategy Table**\n\n"
                "**1. Refined HTF Sweep Filter (1H):**\n"
                "• **Body Close Rule**: Sweep is ONLY valid if the candle body closes back inside the level. Acceptance outside invalidates.\n"
                "• **Wick Proportion**: Wick beyond level must be >= 30% of total candle length.\n"
                "• **Time-to-Reclaim**: Price must trade back inside level within 3 candles.\n"
                "• **Counter-Structure**: Setup is KILLED if price breaks the 'Extreme' before MSS.\n\n"
                "**2. LTF MSS (5m):**\n"
                "• Must occur within 4 hours of sweep.\n\n"
                "**3. RSI Confluence:**\n"
                "• **Longs**: RSI > 40 (Momentum) and < 70 (No Overbought).\n"
                "• **Shorts**: RSI < 60 (Momentum) and > 30 (No Oversold).\n\n"
                "**4. FVG Entry:**\n"
                "• Discount (Longs) or Premium (Shorts).\n"
                "• Spread must be < 5.0."
            )

        else:
            return "❓ Unknown command. Check Menu."

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

    def get_updates(self, offset=None, timeout=10):
        """Check for new messages (commands). Uses Long Polling."""
        if not self.token:
            return []

        try:
            url = f"{self.base_url}/getUpdates"
            params = {"timeout": timeout}
            if offset:
                params["offset"] = offset
            
            # CRITICAL FIX: explicit client-side timeout must be > server-side timeout
            # e.g., if we tell Telegram to wait 10s, we wait 13s mostly.
            # If timeout is small (0.5s for rapid checks), we can be tighter.
            client_timeout = timeout + 3.0 if timeout > 5 else 5.0
            
            response = requests.get(url, params=params, timeout=client_timeout)
            response.raise_for_status()
            return response.json().get("result", [])
        
        except requests.exceptions.ReadTimeout:
            # This is normal if long polling expires without data, but usually API returns empty list properly.
            # However, if network flakes, this triggers. Safe to ignore.
            return []
            
        except requests.exceptions.ConnectionError:
            logger.warning("Telegram Connection Error (Transient). Retrying next cycle...")
            return []

        except Exception as e:
            if "409" in str(e):
                logger.critical("⚠️ TELEGRAM CONFLICT (409): Another instance is running! Please kill old processes.")
            else:
                # Reduce log level for generic fetch errors to avoid spamming user
                logger.debug(f"Failed to get Telegram updates: {e}")
            return []



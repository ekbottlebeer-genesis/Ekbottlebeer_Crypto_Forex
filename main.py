import os
import time
import logging
import json
from datetime import datetime
from dotenv import load_dotenv

from src.communication.telegram_bot import TelegramBot
from src.bridges.mt5_bridge import MT5Bridge
from src.bridges.bybit_bridge import BybitBridge
from src.strategy.session_manager import SessionManager
from src.utils.state_manager import StateManager
from src.strategy.trade_manager import TradeManager
from src.risk.position_sizer import PositionSizer
from src.strategy.smc_logic import SMCLogic
from src.risk.guardrails import RiskGuardrails
from src.utils.visualizer import Visualizer
from src.communication.telegram_handler import TelegramErrorHandler

# --- HELPER: Telegram Command Processing ---
def process_telegram_updates(bot, last_id, context):
    """Checks for and executes Telegram commands (High Responsive)"""
    try:
        # Use short timeout for updates inside scan loop
        updates = bot.get_updates(offset=last_id + 1, timeout=0.1) 
        if updates:
            for update in updates:
                last_id = update['update_id']
                if 'message' in update and 'text' in update['message']:
                    text = update['message']['text']
                    parts = text.split(' ', 1)
                    command = parts[0]
                    args = parts[1] if len(parts) > 1 else ""
                    
                    try:
                        resp = bot.handle_command(command, args, context)
                        if resp:
                            chat_id = update['message']['chat']['id']
                            bot.send_message(resp, chat_id=chat_id)
                    except Exception as cmd_error:
                        # Report Command Failure to User
                        logger.error(f"Command '{command}' crashed: {cmd_error}", exc_info=True)
                        chat_id = update['message']['chat']['id']
                        bot.send_message(f"❌ **COMMAND FAILED**\nError: `{str(cmd_error)}`", chat_id=chat_id)

        return last_id
    except Exception as e:
        logger.error(f"Telegram Update Error: {e}", exc_info=True)
        return last_id

# Setup logging
# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Custom Log Handler for Telegram /logs command
class RingBufferHandler(logging.Handler):
    def __init__(self, capacity=10):
        super().__init__()
        self.capacity = capacity
        self.buffer = []

    def emit(self, record):
        msg = self.format(record)
        self.buffer.append(msg)
        if len(self.buffer) > self.capacity:
            self.buffer.pop(0)
    
    def get_logs(self):
        return "\n".join(self.buffer)

# --- MOCK TELEGRAM FOR OFFLINE / TEST MODE ---
class MockTelegramBot:
    def __init__(self):
        self.running = True
    def get_updates(self, offset=None, timeout=10):
        return []
    def send_message(self, message, chat_id=None):
        logger.info(f"[MOCK TELEGRAM] >> {message[:50]}...")
    def send_signal(self, message):
         logger.info(f"[MOCK SIGNAL] >> {message[:50]}...")
    def send_photo(self, photo_path, caption=""):
        logger.info(f"[MOCK PHOTO] >> {photo_path} | {caption}")
    def handle_command(self, command, args, context):
        return f"Mock Response to {command}"

def get_bot_version():
    """Retrieves the current version (Git Short Hash)."""
    try:
        # Try retrieving git hash
        import subprocess
        ver = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"]).strip().decode('utf-8')
        return f"v1.0.{ver}"
    except:
        return "v1.0.0 (Dev)"

def main():
    """
    Main entry point for the Ekbottlebeer A+ Operator.
    """
    # 1. Load Secrets
    load_dotenv()
    
    VERSION = get_bot_version()
    
    # Initialize RingBuffer for /logs
    log_buffer = RingBufferHandler(capacity=15)
    log_buffer.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(log_buffer) # Add to root logger
    
    logging.info(f"Initializing The Ekbottlebeer A+ Operator [{VERSION}]...")
    print(f"--> BOOTING VERSION: {VERSION}") # Console visibility
    
    # DEBUG: Force print Bybit settings from env
    print(f"--> ENV CHECK: BYBIT_DEMO={os.getenv('BYBIT_DEMO')}")
    print(f"--> ENV CHECK: BYBIT_TESTNET={os.getenv('BYBIT_TESTNET')}")
    
    # Verify presence of secrets (no values shown)
    if os.getenv("BYBIT_API_KEY"): print("--> BYBIT_API_KEY detected.")
    else: print("--> ❌ BYBIT_API_KEY MISSING!")

    # 3. Check for critical environment variables
    chk_vars = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
    missing = [v for v in chk_vars if not os.getenv(v)]
    tele_offline = False
    
    if missing:
        logger.warning(f"⚠️ Missing Telegram Keys: {missing}. Starting in OFFLINE / VERIFICATION MODE.")
        print("--> ⚠️ TELEGRAM OFFLINE. Bot will run without network commands.")
        tele_offline = True
    else:
        # Check Signal Channel (Non-Critical but important)
        if os.getenv("TELEGRAM_SIGNAL_CHANNEL_ID"):
            print("--> SIGNAL CHANNEL: DETECTED (Ready to Broadcast)")
        else:
            print("--> ⚠️ SIGNAL CHANNEL ID MISSING (.env). No signals will be sent.")

    # 3. Initialize Components
    if tele_offline:
        bot = MockTelegramBot()
    else:
        bot = TelegramBot()
    state_manager = StateManager()
    session_manager = SessionManager()
    smc = SMCLogic()
    risk = RiskGuardrails(state_manager)
    visualizer = Visualizer()
    position_sizer = PositionSizer()

    # Initialize Proactive Error Alerting
    error_handler = TelegramErrorHandler(bot)
    error_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(error_handler)

    bot.send_message(f"🚀 System Initializing: The Ekbottlebeer A+ Operator\n📦 **Version**: `{VERSION}`")

    # Connect Bridges
    mt5_bridge = MT5Bridge()
    if mt5_bridge.connect():
        bot.send_message("✅ MT5 Bridge Connected")
    else:
        bot.send_message("⚠️ MT5 Bridge Connection Failed (Check Login/Server)")
        
    bybit_bridge = BybitBridge()
    bot.send_message("✅ Bybit Bridge Initialized")
    
    # Initialize Trade Managers for each bridge
    mt5_trade_manager = TradeManager(mt5_bridge, state_manager, smc_logic=smc, telegram_bot=bot)
    bybit_trade_manager = TradeManager(bybit_bridge, state_manager, smc_logic=smc, telegram_bot=bot)

    # 4. Main Loop
    logger.info("System initialized. Entering main loop...")
    last_heartbeat = time.time()
    last_update_id = 0 # Telegram Offset Tracking
    
    try:
        while True:
            current_time = time.time()
            
            # --- 1. Session & Risk Management ---
             # --- 0. Check Requests (High Priority) ---
            # Shared context for commands
            command_context = {
                'state_manager': state_manager,
                'session_manager': session_manager,
                'risk_manager': risk,
                'visualizer': visualizer,
                'mt5_bridge': mt5_bridge,
                'bybit_bridge': bybit_bridge,
                'smc': smc,
                'position_sizer': position_sizer,
                'logger_buffer': log_buffer,
                'mt5_trade_manager': mt5_trade_manager,
                'bybit_trade_manager': bybit_trade_manager
            }
            last_update_id = process_telegram_updates(bot, last_update_id, command_context)

            # --- 1. Session & Risk Management ---
            # Guard: Check if Session Loss limit is hit
            if risk.check_session_loss():
                logger.info("Session Loss Limit Hit - Scanning Paused for 60s.")
                time.sleep(60)
                continue

            # Protect Active Trades (News)
            active_trades = state_manager.state.get('active_trades', [])
            if active_trades:
                # We need to split trades by bridge/type or handle generically
                # Simplified: Pass assuming bridge argument generic or loop handles
                risk.protect_active_trades(active_trades, mt5_bridge) # TODO: Handle Bybit too

            session_info = session_manager.get_current_session_info()
            current_sessions = session_info['sessions']
            watchlist = set(session_info['watchlist']) # Convert to set for lookup speed
            
            # Identify all symbols with active trades
            active_trade_symbols = {t['symbol'] for t in active_trades}
            

            
            # Combine loop: Watchlist (Hunting) + Active Trades (Managing)
            all_monitored_symbols = watchlist.union(active_trade_symbols)
            
            # Combine loop: Watchlist (Hunting) + Active Trades (Managing)
            all_monitored_symbols = watchlist.union(active_trade_symbols)
            
            # --- 1.5. Manage Pending Setups (Reaction Mode) ---
            pending_setups = state_manager.state.get('pending_setups', [])
            for setup in pending_setups[:]: # Copy to iterate
                symbol = setup['symbol']
                bridge = bybit_bridge if symbol in session_manager.crypto_symbols else mt5_bridge
                
                # 1. Expiration (2h)
                try:
                    created_ts = datetime.fromisoformat(setup['created_at'])
                    if (datetime.now() - created_ts).total_seconds() > 7200:
                        state_manager.remove_pending_setup(symbol)
                        continue
                except: pass

                # 2. Check Reaction
                ltf_tf = '5' if bridge == bybit_bridge else 5
                candles = bridge.get_candles(symbol, timeframe=ltf_tf, num_candles=2)
                if candles is None or candles.empty: continue
                
                last = candles.iloc[-1]
                entry_level = setup['entry']
                direction = setup['direction']
                triggered = False
                
                # LOGIC: Tap + Reject + Color
                if direction == 'bullish':
                     if last['low'] <= entry_level and last['close'] > entry_level and last['close'] > last['open']:
                         triggered = True
                     # Invalidation: Close below SL
                     if last['close'] < setup['sl']:
                         state_manager.remove_pending_setup(symbol)
                         continue
                else:
                     if last['high'] >= entry_level and last['close'] < entry_level and last['close'] < last['open']:
                         triggered = True
                     # Invalidation
                     if last['close'] > setup['sl']:
                         state_manager.remove_pending_setup(symbol)
                         continue
                         
                if triggered:
                     # EXECUTE MARKET ORDER
                     balance = bridge.get_balance()
                     inst_info = bridge.get_instrument_info(symbol)
                     units = position_sizer.calculate_position_size(balance, setup['entry'], setup['sl'], symbol, instrument_info=inst_info)
                     
                     if units > 0:
                         logger.info(f"⚡ REACTION CONFIRMED: {symbol}. FIRING MARKET ORDER.")
                         res_ticket = None
                         if bridge == bybit_bridge:
                             side = 'Buy' if direction == 'bullish' else 'Sell'
                             res_ticket = bridge.place_order(symbol, side, 'Market', units, stop_loss=setup['sl'], take_profit=setup['tp'])
                         else:
                             o_type = 'market_buy' if direction == 'bullish' else 'market_sell'
                             res_ticket = bridge.place_limit_order(symbol, o_type, 0.0, setup['sl'], setup['tp'], units)
                         
                         if res_ticket:
                             bot.send_message(f"⚡ **REACTION HIT**: Executed Market Order on {symbol}\nTicket: `{res_ticket}`")
                             state_manager.remove_pending_setup(symbol)
                         else:
                             # Retry logic (Half Risk)
                             half_units = units * 0.5
                             if bridge == bybit_bridge:
                                 res_ticket = bridge.place_order(symbol, side, 'Market', half_units, stop_loss=setup['sl'], take_profit=setup['tp'])
                             else:
                                 res_ticket = bridge.place_limit_order(symbol, o_type, 0.0, setup['sl'], setup['tp'], half_units)
                             
                             if res_ticket:
                                 bot.send_message(f"⚠️ **RESCUE**: Executed Half Risk on {symbol}")
                                 state_manager.remove_pending_setup(symbol)
                     else:
                         bot.send_message(f"⚠️ Low Balance for Reaction Trade: {symbol}")
                         state_manager.remove_pending_setup(symbol)

            # --- 2. Market Scan Loop ---
            
            # Print Header
            t_str = datetime.now().strftime('%H:%M:%S')
            # Filter Lists
            paused_list = []
            news_list = []
            spread_list = []
            active_count = 0
            
            for i, symbol in enumerate(all_monitored_symbols):
                # High-Frequency Command check (every 2 symbols)
                if i % 2 == 0:
                    last_update_id = process_telegram_updates(bot, last_update_id, command_context)
                # Bridge Selection
                bridge = None
                trade_mgr = None
                if symbol in session_manager.crypto_symbols:
                    bridge = bybit_bridge
                    trade_mgr = bybit_trade_manager
                else:
                    bridge = mt5_bridge
                    trade_mgr = mt5_trade_manager

                # Only proceed if bridge connected/active (Stub check)
                
                # --- A. Manage Active Trades (Trailing, TP) ---
                # Always run this regardless of session correctness
                symbol_trades = [t for t in active_trades if t['symbol'] == symbol]
                if symbol_trades:
                    # Fetch data needed for management
                    tick = bridge.get_tick(symbol)
                    
                    # optimized: Reuse LTF fetch if we are about to fetch it anyway?
                    # For safety, fetch fresh 5m candles for trailing logic
                    mt_tf = '5' if bridge == bybit_bridge else 5
                    mgmt_candles = bridge.get_candles(symbol, timeframe=mt_tf, num_candles=10)
                    
                    if tick:
                        current_price = tick['bid'] # default to bid for check
                        for trade in symbol_trades:
                            # Use Ask for Short closing? Simplify to mid or Bid for now.
                            # Accurate: Long exits on Bid, Short exits on Ask.
                            # price_to_check = tick['bid'] if trade['direction'] == 'long' else tick['ask'] # Correction: Long closes on Bid, Short on Ask. Correct.
                            price_to_check = tick['bid'] if trade['direction'] == 'long' else tick['ask']
                            trade_mgr.manage_active_trade(trade, price_to_check, ltf_candles=mgmt_candles)
                    
                    # CRITICAL: If we have an active trade, DO NOT HUNT for new ones on this symbol.
                    # Prevent stacking/double entry.
                    continue

                # --- B. Hunt for Setups (SMC Logic) ---
                # Check Global Status
                system_status = state_manager.state.get('system_status', 'active')
                
                # Check Granular Status
                is_crypto = symbol in session_manager.crypto_symbols
                market_status = state_manager.state.get('crypto_status', 'active') if is_crypto else state_manager.state.get('forex_status', 'active')
                
                # OLD SESSION KILLA REMOVED per user request.
                # Asia hunting is back ON.
                # if is_asia and not is_crypto: ... (Deleted)

                # Scan Condition: 
                # 1. Symbol in Session Watchlist
                # 2. Global System Active
                # 3. Specific Market Active
                
                if symbol not in watchlist: continue
                
                if system_status == 'paused' or market_status == 'paused':
                     paused_list.append(symbol)
                     continue
                
                # 1. Check News Filter
                if not risk.check_news(symbol):
                    news_list.append(symbol)
                    continue
                    
                # 1.5. Spread Protection (Crucial for Scalping)
                # Fetch live tick first
                tick_scan = bridge.get_tick(symbol)
                if not tick_scan: continue
                
                spread = tick_scan['ask'] - tick_scan['bid']
                
                if not risk.check_spread(symbol, spread, max_spread_pips=5.0): # 5 pips/points flexible
                     spread_list.append(symbol)
                     continue
                
                active_count += 1
                    
                # 2. Fetch Data (HTF - 1H)
                # MT5: 1H=16385, Bybit: '60'
                htf_tf = '60' if bridge == bybit_bridge else 16385
                htf_candles = bridge.get_candles(symbol, timeframe=htf_tf, num_candles=100)
                
                if htf_candles is None or htf_candles.empty:
                    continue

                # 3. Detect HTF Sweep
                sweep = smc.detect_htf_sweeps(htf_candles)
                
                if not sweep['swept']:
                    # HUD v2: Detailed Status (RSI + Bias) for Neutral Assets
                    ltf_tf_scan = '5' if bridge == bybit_bridge else 5
                    ltf_scan_data = bridge.get_candles(symbol, timeframe=ltf_tf_scan, num_candles=50)
                    
                    status_line = f"⏩ [NEUTRAL] Wait HTF Sweep"
                    rsi_val = 50.0
                    bias = "NEUTRAL"
                    
                    if ltf_scan_data is not None and not ltf_scan_data.empty:
                        try:
                            ltf_scan_data['rsi'] = smc.calculate_rsi(ltf_scan_data['close'], 14)
                            rsi_val = ltf_scan_data.iloc[-1]['rsi']
                            if rsi_val > 60: bias = "BULLISH"
                            elif rsi_val < 40: bias = "BEARISH"
                            
                            status_line = f"{bias:<7} | RSI: {rsi_val:>4.1f} | Wait HTF Sweep"
                        except: pass
                    
                    # Persist for Dashboard
                    waiting_on = f"Sweep High: {sweep.get('htf_high', 0):.5f} / Low: {sweep.get('htf_low', 0):.5f}"
                    state_manager.update_scan_data(symbol, {
                        'bias': bias, 'rsi': rsi_val, 'status': "Scanning", 'waiting_on': waiting_on, 'checkpoint': 'SWEEP'
                    })
                    print(f"   📊 {symbol:<10} | {status_line}")
                    continue
                
                # --- SWEEP DETECTED ---
                if sweep['swept']:
                    side_name = "BEARISH (Short Setup)" if sweep['side'] == 'buy_side' else "BULLISH (Long Setup)"
                    
                    # 4. Drop to LTF (5m) for MSS
                    ltf_tf = '5' if bridge == bybit_bridge else 5
                    ltf_candles = bridge.get_candles(symbol, timeframe=ltf_tf, num_candles=200)
                    if ltf_candles is None or ltf_candles.empty: continue

                    mss = smc.detect_mss(ltf_candles, sweep['side'], sweep['sweep_candle_time'])
                    
                    # Log MSS Failure reason
                    if not mss.get('mss', False):
                        reason = mss.get('reason', 'Wait MSS break')
                        trigger = mss.get('trigger_level', 0)
                        type_str = mss.get('type', 'cross')
                        
                        status_msg = f"⏱️ Wait MSS {type_str} {trigger:.5f}"
                        if reason == 'Expired': status_msg = "❌ Setup Expired (>4h)"
                        
                        logger.info(f"   👀 {symbol:<10} | Sweep ✅ | {status_msg}")
                        state_manager.update_scan_data(symbol, {
                            'bias': 'BULLISH' if sweep['side'] == 'sell_side' else 'BEARISH',
                            'rsi': 0, 'status': "Sweep Confirmed", 'waiting_on': status_msg, 'checkpoint': 'MSS'
                        })
                        continue
                    
                    # --- MSS CONFIRMED ---
                    if mss.get('mss', False):
                        # Calculate RSI for confluence check
                        ltf_candles['rsi'] = smc.calculate_rsi(ltf_candles['close'], 14)
                        current_rsi = ltf_candles.iloc[-1]['rsi']

                        # Filter Logic (Strictly Matches README Strategy)
                        rsi_ok = False
                        if sweep['side'] == 'buy_side': # We swept highs -> Bearish Bias (Short)
                             # Strategy: RSI < 60 (Momentum) and > 30 (No Oversold)
                             if (30 <= current_rsi <= 60): 
                                rsi_ok = True
                             else:
                                logger.warning(f"   📉 {symbol:<10} | MSS ✅ | RSI WARNING: {current_rsi:.1f} (Ideal 30-60)")
                        else: # We swept lows -> Bullish Bias (Long)
                             # Strategy: RSI > 40 (Momentum) and < 70 (No Overbought)
                             if (40 <= current_rsi <= 70): 
                                rsi_ok = True
                             else:
                                logger.warning(f"   📈 {symbol:<10} | MSS ✅ | RSI WARNING: {current_rsi:.1f} (Ideal 40-70)")
                        
                        # UPDATED RULE 4: RSI is PERMISSION ONLY. Structure Overrides.
                        # We do NOT continue/skip here. We just log the warning above.
                        # if not rsi_ok: continue <-- REMOVED
                        
                        # 5. Find FVG Entry (Premium/Discount Linked)
                        direction_bias = 'bearish' if sweep['side'] == 'buy_side' else 'bullish'
                        fvgs = smc.find_fvg(ltf_candles, direction_bias, mss['leg_high'], mss['leg_low'])
                        
                        if not fvgs:
                            logger.info(f"   🔍 {symbol:<10} | MSS ✅ | RSI ✅ | Wait FVG in {direction_bias} zone")
                            state_manager.update_scan_data(symbol, {
                                'bias': direction_bias.upper(), 'rsi': current_rsi, 'status': "Wait FVG", 'waiting_on': "Formation in Prem/Disc", 'checkpoint': 'FVG'
                            })
                            continue
                        
                        if fvgs:
                             fvg = fvgs[0]
                             logger.info(f"💎 A+ SETUP: {symbol} {direction_bias.upper()} FVG @ {fvg['entry']}")
                             
                             # Dash: Update status for execution
                             state_manager.update_scan_data(symbol, {
                                 'bias': direction_bias.upper(),
                                 'rsi': current_rsi,
                                 'status': "💎 FVG FOUND",
                                 'waiting_on': "Execution",
                                 'checkpoint': 'EXEC'
                             })
                        
                        if fvgs:
                            setup = fvgs[0] # Take the most recent/valid FVG
                            entry_price = setup['entry']
                            
                             # Stop Loss Calculation
                            # Rule: SL at the Sweep Candle High/Low (Pivot)
                            # mss['leg_high'] is the high of the breakdown move for bearish
                            # For Bearish: SL should be the High that caused the low.
                            sl_price = mss['leg_high'] if direction_bias == 'bearish' else mss['leg_low']
                            
                            # SAFETY BUFFER (Optional, per user request "small buffer for fees" logic elsewhere)
                            # For SL, exact pivot is standard SMC.
                            
                            # TP Calculation: 1:2 Minimum
                            risk_dist = abs(entry_price - sl_price)
                            tp_price = entry_price - (2 * risk_dist) if direction_bias == 'bearish' else entry_price + (2 * risk_dist)
                            
                            # 6. Risk Check & Execution
                            balance = bridge.get_balance()
                            
                            # Calculate Stats
                            rr_ratio = abs(tp_price - entry_price) / risk_dist if risk_dist > 0 else 0
                            
                            # Construct Signal
                            signal_msg = (
                                f"💎 **A+ SETUP FOUND** 💎\n\n"
                                f"📜 **Symbol**: `{symbol}`\n"
                                f"↕️ **Side**: {direction_bias.upper()}\n"
                                f"📉 **Entry**: `{entry_price:.5f}`\n"
                                f"🛑 **Stop Loss**: `{sl_price:.5f}`\n"
                                f"🎯 **Take Profit**: `{tp_price:.5f}`\n\n"
                                f"⚖️ **R:R**: `1:{rr_ratio:.2f}`\n"
                                f"📅 **Time**: `{datetime.now().strftime('%H:%M UTC')}`"
                            )
                            
                            bot.send_signal(signal_msg)
                            
                            # --- 7. AUTO-EVIDENCE: Generate & Send Chart ---
                            try:
                                h1_high = htf_candles['high'].tail(24).max()
                                h1_low = htf_candles['low'].tail(24).min()
                                
                                evidence_zones = {
                                    'sweeps': [{'price': sweep['level'], 'desc': sweep['desc']}],
                                    'mss': [{'time': ltf_candles.iloc[-1]['time'], 'price': mss['level']}],
                                    'fvg': [setup],
                                    'htf': {
                                        '1H_high': h1_high,
                                        '1H_low': h1_low
                                    },
                                    'trade': {
                                        'entry': entry_price,
                                        'sl': sl_price,
                                        'tp': tp_price
                                    }
                                }
                                # Generate Chart (Synchronous)
                                evidence_path = visualizer.generate_chart(ltf_candles, symbol, zones=evidence_zones, filename=f"evidence_{symbol}_{int(time.time())}.png")
                                
                                if evidence_path and os.path.exists(evidence_path):
                                    caption = f"📸 **Trade Evidence**: {symbol} {direction_bias.upper()}\nEntry: {entry_price} | SL: {sl_price} | TP: {tp_price}"
                                    bot.send_photo(evidence_path, caption=caption)
                                    # cleanup? os.remove(evidence_path) # Optional, keep for debug for now
                            except Exception as e_vis:
                                logger.error(f"Failed to generate auto-evidence chart: {e_vis}")

                            if position_sizer.check_risk_reward(entry_price, sl_price, tp_price):
                                # NEW EXECUTION LOGIC: Wait for Reaction
                                logger.info(f"💎 A+ SETUP QUEUED for {symbol}. Waiting for Reaction Candle...")
                                
                                setup_data = {
                                    'symbol': symbol,
                                    'direction': direction_bias, # 'bullish' or 'bearish'
                                    'entry': entry_price,
                                    'sl': sl_price,
                                    'tp': tp_price,
                                    'created_at': datetime.now().isoformat(),
                                    'fvg_bottom': setup.get('bottom', entry_price),
                                    'fvg_top': setup.get('top', entry_price)
                                }
                                state_manager.add_pending_setup(setup_data)
                                
                                bot.send_message(
                                    f"⏳ **SETUP QUEUED**: {symbol} {direction_bias.upper()}\n"
                                    f"Waiting for **Reaction Candle** at `{entry_price:.5f}`..."
                                )
                            else:
                                bot.send_message(f"⚠️ **RR INVALID**: {symbol} setup found but RR < 2.0 (Calculated: {rr_ratio:.2f})") 
            
            # --- Loop Summary ---
            t_now = datetime.now().strftime('%H:%M:%S')
            summary_parts = [f"[{t_now}] 🔍 Active: {active_count}"]
            if news_list: summary_parts.append(f"News Halt: {len(news_list)}")
            if paused_list: summary_parts.append(f"Paused: {len(paused_list)}")
            if spread_list: summary_parts.append(f"High Spread: {len(spread_list)}")
            
            print(" | ".join(summary_parts))

            # --- 3. Heartbeat Logic (Every 60 mins) ---
            if current_time - last_heartbeat > 3600:
                status_msg = f"💓 System Heartbeat\nSessions: {current_sessions}\nWatchlist Size: {len(watchlist)}"
                bot.send_message(status_msg)
                last_heartbeat = current_time
                state_manager.save_state()
            


            time.sleep(3) # Scan delay
            
    except KeyboardInterrupt:
        logger.info("Shutdown signal received.")
        bot.send_message("🛑 System Shutdown Initiated via Keyboard")
        mt5_bridge.shutdown()
        
    except Exception as e:
        logger.critical(f"CRITICAL CRASH: {e}", exc_info=True)
        bot.send_message(f"🚨 **SYSTEM CRASHED** 🚨\nError: `{str(e)}`\nCheck logs immediately.")
        mt5_bridge.shutdown()
        raise e # Re-raise to let watchdog restart if needed

if __name__ == "__main__":
    main()

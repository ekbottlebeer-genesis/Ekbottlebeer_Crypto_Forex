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

    # 2. Check for critical environment variables
    chk_vars = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
    missing = [v for v in chk_vars if not os.getenv(v)]
    if missing:
        logger.error(f"Missing environment variables: {missing}")
        return

    # 3. Initialize Components
    bot = TelegramBot()
    state_manager = StateManager()
    session_manager = SessionManager()
    smc = SMCLogic()
    risk = RiskGuardrails(state_manager)
    visualizer = Visualizer()
    position_sizer = PositionSizer()

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
    
    try:
        while True:
            current_time = time.time()
            
            # --- 1. Session & Risk Management ---
            # Check if Session Loss limit is hit
            if risk.check_session_loss():
                logger.info("Session Loss Limit Hit - Scanning Paused.")
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
            
            # --- 2. Market Scan Loop ---
            for symbol in all_monitored_symbols:
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

                # --- B. Hunt for Setups (SMC Logic) ---
                # ONLY run this if the symbol is in the ACTIVE SESSION WATCHLIST
                # Also check PAUSE status
                system_status = state_manager.state.get('system_status', 'active')
                
                if symbol not in watchlist or system_status == 'paused':
                    # logger.debug(f"Skipping Search for {symbol} (Out of Session/Paused)")
                    continue
                
                # 1. Check News Filter
                if not risk.check_news(symbol):
                    continue
                    
                # 1.5. Spread Protection (Crucial for Scalping)
                # Fetch live tick first
                tick_scan = bridge.get_tick(symbol)
                if not tick_scan: continue
                
                spread = tick_scan['ask'] - tick_scan['bid']
                # Define max spread (e.g. 2.0 pips for FX, or ratio for Crypto)
                # For MVP: Hardcoded safety or config?
                # FX: 0.00020 (2 pips in 5-digit broker is 20 points).
                # Crypto: $0.50 on BTC?
                # Let's trust risk.check_spread defaults or pass reasonable threshold.
                
                # Using a generic buffer. Ideally configurable per asset class.
                # FX Pips vs Crypto Price.
                # Simplified: If spread > 0.0003 (3 pips) for Forex pairs.
                # Guardrails should handle the logic, we pass value.
                
                if not risk.check_spread(symbol, spread, max_spread_pips=5.0): # 5 pips/points flexible
                     # logger.debug(f"Skipping {symbol} due to spread {spread:.5f}")
                     continue
                    
                # 2. Fetch Data (HTF - 1H)
                # MT5: 1H=16385, Bybit: '60'
                htf_tf = '60' if bridge == bybit_bridge else 16385
                htf_candles = bridge.get_candles(symbol, timeframe=htf_tf, num_candles=100)
                
                if htf_candles is None or htf_candles.empty:
                    continue

                # 3. Detect HTF Sweep
                sweep = smc.detect_htf_sweeps(htf_candles)
                
                if sweep['swept']:
                    logger.info(f"🚨 HTF Sweep Detected on {symbol}: {sweep['desc']} @ {sweep['level']}")
                    
                    # 4. Drop to LTF (5m) for MSS
                    # MT5: 5m=5, Bybit: '5'
                    ltf_tf = '5' if bridge == bybit_bridge else 5
                    ltf_candles = bridge.get_candles(symbol, timeframe=ltf_tf, num_candles=200)
                    
                    if ltf_candles is None or ltf_candles.empty:
                        continue

                    mss = smc.detect_mss(ltf_candles, sweep['side'], sweep['sweep_candle_time'])
                    
                    if mss.get('mss', False):
                        logger.info(f"⚡ MSS Confirmed on {symbol} @ {mss['level']}")
                        
                        # 5. Find FVG Entry (Premium/Discount Linked)
                        direction_bias = 'bearish' if sweep['side'] == 'buy_side' else 'bullish'
                        fvgs = smc.find_fvg(ltf_candles, direction_bias, mss['leg_high'], mss['leg_low'])
                        
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
                                evidence_zones = {
                                    'sweeps': [{'price': sweep['level'], 'desc': sweep['desc']}],
                                    'mss': [{'time': ltf_candles.iloc[-1]['time'], 'price': mss['level']}],
                                    'fvg': [setup],
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
                                units = position_sizer.calculate_position_size(balance, entry_price, sl_price, symbol)
                                
                                if units > 0:
                                    logger.info(f"🚀 EXECUTING {direction_bias.upper()} on {symbol}. Units: {units:.4f}")
                                    
                                    result_ticket = None
                                    if bridge == bybit_bridge:
                                        side = 'Buy' if direction_bias == 'bullish' else 'Sell'
                                        # Use standard place_order
                                        result_ticket = bridge.place_order(symbol, side, 'Limit', units, price=entry_price, stop_loss=sl_price, take_profit=tp_price)
                                    else:
                                        o_type = 'buy_limit' if direction_bias == 'bullish' else 'sell_limit'
                                        result_ticket = bridge.place_limit_order(symbol, o_type, entry_price, sl_price, tp_price, units)
                                    
                                    if result_ticket:
                                        exec_msg = (
                                            f"🚀 **ORDER EXECUTED** 🚀\n"
                                            f"{symbol} {direction_bias.upper()} Limit Placed.\n"
                                            f"📦 **Qty**: `{units:.4f}`\n"
                                            f"🎫 **Ticket**: `{result_ticket}`"
                                        )
                                        bot.send_message(exec_msg)
                                    else:
                                        # RETRY LOGIC: Half Risk Rescue
                                        logger.warning(f"⚠️ Order failed for {symbol}. Retrying with HALF RISK...")
                                        
                                        half_units = units * 0.5
                                        # Ensure min volume check logic applies? 
                                        # Or just rely on bridges to reject again if too small.
                                        
                                        half_ticket = None
                                        if bridge == bybit_bridge:
                                            half_ticket = bridge.place_order(symbol, side, 'Limit', half_units, price=entry_price, stop_loss=sl_price, take_profit=tp_price)
                                        else:
                                            half_ticket = bridge.place_limit_order(symbol, o_type, entry_price, sl_price, tp_price, half_units)
                                            
                                        if half_ticket:
                                            rescue_msg = (
                                                f"⚠️ **MARGIN RESCUE EXECUTED** ⚠️\n"
                                                f"{symbol} Limit Placed at **HALF RISK**.\n"
                                                f"📦 **Qty**: `{half_units:.4f}` (Reduced)\n"
                                                f"🎫 **Ticket**: `{half_ticket}`"
                                            )
                                            bot.send_message(rescue_msg)
                                        else:
                                            bot.send_message(f"❌ **EXECUTION FAILED**: {symbol} rejected even at Half Risk.")
                                else:
                                    bot.send_message(f"⚠️ **MARGIN LOW**: {symbol} found but 0 units calculated. (Balance: {balance:.2f})")
                            else:
                                bot.send_message(f"⚠️ **RR INVALID**: {symbol} setup found but RR < 2.0 (Calculated: {rr_ratio:.2f})") 
            
            # --- 3. Heartbeat Logic (Every 60 mins) ---
            if current_time - last_heartbeat > 3600:
                status_msg = f"💓 System Heartbeat\nSessions: {current_sessions}\nWatchlist Size: {len(watchlist)}"
                bot.send_message(status_msg)
                last_heartbeat = current_time
                state_manager.save_state()
            
            # --- 4. Check Requests ---
            updates = bot.get_updates()
            if updates:
                context = {
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
                for update in updates:
                    if 'message' in update and 'text' in update['message']:
                        text = update['message']['text']
                        # Simple argument parsing
                        parts = text.split(' ', 1)
                        command = parts[0]
                        args = parts[1] if len(parts) > 1 else ""
                        
                        bot.handle_command(command, args, context)

            time.sleep(5) # Scan delay
            
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

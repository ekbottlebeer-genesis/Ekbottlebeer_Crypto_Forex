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

def main():
    """
    Main entry point for the Ekbottlebeer A+ Operator.
    """
    # 1. Load Secrets
    load_dotenv()
    logger.info("Initializing The Ekbottlebeer A+ Operator...")

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

    bot.send_message("🚀 System Initializing: The Ekbottlebeer A+ Operator")

    # Connect Bridges
    mt5_bridge = MT5Bridge()
    if mt5_bridge.connect():
        bot.send_message("✅ MT5 Bridge Connected")
    else:
        bot.send_message("⚠️ MT5 Bridge Connection Failed (Check Login/Server)")

    bybit_bridge = BybitBridge()
    bot.send_message("✅ Bybit Bridge Initialized")
    
    # Initialize Trade Managers for each bridge
    mt5_trade_manager = TradeManager(mt5_bridge, state_manager)
    bybit_trade_manager = TradeManager(bybit_bridge, state_manager)

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
            watchlist = session_info['watchlist']
            
            # --- 2. Market Scan Loop ---
            for symbol in watchlist:
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
                # Find active trades for this symbol
                symbol_trades = [t for t in active_trades if t['symbol'] == symbol]
                for trade in symbol_trades:
                    # Get current price
                    # tick = bridge.get_tick(symbol)
                    # trade_mgr.manage_active_trade(trade, tick['bid'])
                    pass

                # --- B. Hunt for Setups (SMC Logic) ---
                
                # 1. Check News Filter
                if not risk.check_news(symbol):
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
                                         bot.send_message(f"⚠️ **EXECUTION ERROR**: {symbol} found but Broker rejected order.")
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
                    'smc': smc
                }
                for update in updates:
                    if 'message' in update and 'text' in update['message']:
                        text = update['message']['text']
                        # Simple argument parsing
                        parts = text.split(' ', 1)
                        command = parts[0]
                        args = parts[1] if len(parts) > 1 else ""
                        
                        response = bot.handle_command(command, args, context)
                        if response:
                            bot.send_message(response)

            time.sleep(5) # Scan delay
            
    except KeyboardInterrupt:
        logger.info("Shutdown signal received.")
        bot.send_message("🛑 System Shutdown Initiated")
        mt5_bridge.shutdown()

if __name__ == "__main__":
    main()

# src/strategy/trade_manager.py
import logging

logger = logging.getLogger(__name__)

class TradeManager:
    def __init__(self, bridge, state_manager):
        self.bridge = bridge
        self.state_manager = state_manager

    def manage_active_trade(self, trade, current_price, ltf_candles=None):
        """
        Block 3.2: Trade Lifecycle & Trailing Management.
        
        Rules:
        1. BE Trigger: At 1.5R, move SL to (Entry - 0.25R buffer).
        2. Partial TP: At 2.0R, close 30%.
        3. Trailing SL: Post 2.0R, trail behind recent structure.
        """
        symbol = trade['symbol']
        entry_price = trade['entry_price']
        sl_price = trade['sl_price']
        direction = trade['direction'] # 'long' or 'short'
        
        # Calculate R (Risk unit)
        r_distance = abs(entry_price - sl_price)
        
        # Calculate current profit distance
        current_distance = 0
        if direction == 'long':
            current_distance = current_price - entry_price
        else:
            current_distance = entry_price - current_price
            
        current_r = current_distance / r_distance
        
        # 1. Break-Even Check (1.5R)
        if current_r >= 1.5 and not trade.get('is_be', False):
            # Move SL to Entry + 0.25R (Buffer) matches specific prompt:
            # "move the Stop Loss to -0.25R (entry price plus a small buffer for fees)"
            # Wait, user said "-0.25R" relative to risk? 
            # Usually BE means Entry. -0.25R implies locking in a small loss? 
            # Or locking in 0.25R profit? "entry price plus a small buffer" implies profit.
            # Let's assume locking in 0.25R Profit.
            
            buffer = 0.25 * r_distance
            new_sl = 0
            
            if direction == 'long':
                new_sl = entry_price + buffer
            else:
                new_sl = entry_price - buffer
                
            logger.info(f"Triggering BE for {symbol} at {current_r:.2f}R. New SL: {new_sl}")
            self.bridge.modify_order(trade['ticket'], sl=new_sl)
            trade['sl_price'] = new_sl
            trade['is_be'] = True
            self.state_manager.save_state()

        # 2. Partial TP (2.0R)
        if current_r >= 2.0 and not trade.get('partial_taken', False):
            logger.info(f"Triggering Partial TP (30%) for {symbol} at {current_r:.2f}R")
            # Close 30%
            self.bridge.close_position(trade['ticket'], pct=0.3)
            trade['partial_taken'] = True
            self.state_manager.save_state()
            
        # 3. Trailing SL (Post 2.0R)
        if current_r >= 2.0 and ltf_candles is not None and not ltf_candles.empty:
            # Trailing Logic: Trail behind the extreme of the last 3 closed candles
            # This is a robust way to trail market structure without complex swing detection
            
            last_3 = ltf_candles.iloc[-4:-1] # Exclude current forming candle
            
            new_trail_sl = None
            
            if direction == 'long':
                # Long: Trail below the lowest low of recent price action
                recent_low = last_3['low'].min()
                # Ensure we only move SL UP
                if recent_low > sl_price:
                    new_trail_sl = recent_low
            else:
                # Short: Trail above the highest high
                recent_high = last_3['high'].max()
                # Ensure we only move SL DOWN
                if recent_high < sl_price:
                    new_trail_sl = recent_high
            
            if new_trail_sl:
                 # Buffer? Maybe small buffer or exact extreme.
                 logger.info(f"Trailing SL Updated for {symbol}. Old: {sl_price} -> New: {new_trail_sl}")
                 if self.bridge.modify_order(trade['ticket'], sl=new_trail_sl):
                     trade['sl_price'] = new_trail_sl
                     self.state_manager.save_state()

        return trade

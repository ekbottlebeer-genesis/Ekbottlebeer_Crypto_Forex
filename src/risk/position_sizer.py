# src/risk/position_sizer.py
import logging

logger = logging.getLogger(__name__)

class PositionSizer:
    def __init__(self):
        self.default_risk_pct = 1.0 # 1% Risk
        self.min_rr = 2.0
    
    def calculate_position_size(self, account_balance, entry_price, sl_price, symbol, instrument_info=None):
        """
        Calculates position size (Lots/Contracts).
        Formula: (Risk Amount / Risk Distance) / Contract Size
        Then rounded to Volume Step.
        """
        if account_balance <= 0 or not instrument_info: return 0.0
        
        risk_amount = account_balance * (self.default_risk_pct / 100.0)
        risk_distance = abs(entry_price - sl_price)
        
        if risk_distance == 0: return 0.0
        
        # 1. Raw Units (Base Currency)
        # E.g. Risk $100 / $0.001 dist = 100,000 units
        raw_units = risk_amount / risk_distance
        
        # 2. Convert to Lots/Contracts
        contract_size = instrument_info.get('contract_size', 1.0)
        lots = raw_units / contract_size
        
        # 3. Apply Limits (Min/Max/Step)
        min_vol = instrument_info.get('min_volume', 0.01)
        max_vol = instrument_info.get('max_volume', 100.0)
        step = instrument_info.get('volume_step', 0.01)
        
        # Round to step
        if step > 0:
            lots = round(lots / step) * step
            
        # Clamp
        if lots < min_vol:
             logger.warning(f"Calculated size {lots} < Min {min_vol} for {symbol}. Skipping.")
             return 0.0
        if lots > max_vol: lots = max_vol
        
        # Final precision fix (avoid 0.1000000001)
        decimals = str(step)[::-1].find('.')
        if decimals < 0: decimals = 2
        lots = round(lots, decimals)
        
        return lots

    def check_risk_reward(self, entry_price, sl_price, tp_price):
        """
        Validates if the trade meets the minimum 2.0 Risk:Reward ratio.
        """
        risk = abs(entry_price - sl_price)
        reward = abs(tp_price - entry_price)
        
        if risk == 0: return False
        
        rr_ratio = reward / risk
        
        if rr_ratio < self.min_rr:
            logger.info(f"RR Check Failed: {rr_ratio:.2f} < {self.min_rr}")
            return False
            
        return True

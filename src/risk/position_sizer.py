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
        if account_balance <= 0:
            logger.warning(f"Position Sizer: Zero or negative balance ({account_balance}) for {symbol}")
            return 0.0
        if not instrument_info:
            logger.warning(f"Position Sizer: Missing instrument info for {symbol}. Cannot calculate size.")
            return 0.0
        
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
             # AUTO-SCALE: If calculated risk is small but below min_lot, force min_lot
             # Provided it doesn't exceed a HARD RISK CEILING (e.g. 3%)
             # This solves the "$500 account can't trade Gold" issue.
             
             # Calculate Risk of Min Vol
             min_vol_risk_money = (min_vol * contract_size) * risk_distance
             risk_pct_actual = (min_vol_risk_money / account_balance) * 100
             
             if risk_pct_actual <= 3.0:
                 logger.info(f"Size Adjustment: Calculated {lots} < Min {min_vol}. Upgrading to {min_vol} (Risk: {risk_pct_actual:.2f}%)")
                 lots = min_vol
             else:
                 logger.warning(f"Calculated size {lots} < Min {min_vol}. Upgrade rejected (Risk {risk_pct_actual:.2f}% > 3%). Skipping.")
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

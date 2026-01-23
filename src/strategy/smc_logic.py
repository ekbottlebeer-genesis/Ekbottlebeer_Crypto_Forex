# src/strategy/smc_logic.py
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

class SMCLogic:
    def __init__(self):
        self.swing_lookback = 3 

    def find_swings(self, df: pd.DataFrame):
        """
        Identifies swing highs and lows based on the 3-candle pivot rule.
        Adds 'is_swing_high', 'swing_high_val', 'is_swing_low', 'swing_low_val' columns.
        """
        df['is_swing_high'] = False
        df['swing_high_val'] = np.nan
        df['is_swing_low'] = False
        df['swing_low_val'] = np.nan
        
        # 3-Candle Pattern: i-1 is the pivot. 
        # High[i-1] > High[i-2] AND High[i-1] > High[i] -> Swing High at i-1
        # Low[i-1] < Low[i-2] AND Low[i-1] < Low[i] -> Swing Low at i-1
        # We iterate from index 2 to len-1 (need i-2, i-1, i)
        
        for i in range(2, len(df)):
            # Check Swing High
            if (df['high'].iloc[i-1] > df['high'].iloc[i-2]) and (df['high'].iloc[i-1] > df['high'].iloc[i]):
                df.at[df.index[i-1], 'is_swing_high'] = True
                df.at[df.index[i-1], 'swing_high_val'] = df['high'].iloc[i-1]
            
            # Check Swing Low
            if (df['low'].iloc[i-1] < df['low'].iloc[i-2]) and (df['low'].iloc[i-1] < df['low'].iloc[i]):
                df.at[df.index[i-1], 'is_swing_low'] = True
                df.at[df.index[i-1], 'swing_low_val'] = df['low'].iloc[i-1]
                
        return df

    def detect_htf_sweeps(self, htf_candles: pd.DataFrame):
        if len(htf_candles) < 20: return {'swept': False}

        # Lookback Window
        lookback = 20
        # Fix: Must exclude the 'prev_candle' (index -2) from the Max/Min calc
        # Slice: from -(20+2) up to -2
        df = htf_candles.iloc[-(lookback+2):-2] 
        
        # print(f"DEBUG: Checking Sweep on {len(df)} candles. High: {df['high'].max()}") 
        
        current_candle = htf_candles.iloc[-1]
        prev_candle = htf_candles.iloc[-2]
        
        period_high = df['high'].max()
        period_low = df['low'].min()
        
        # Check Buy Side Sweep (Short Bias)
        if prev_candle['high'] > period_high and prev_candle['close'] < period_high:
             touch_count = df[df['high'] > (period_high * 0.9998)].shape[0]
             desc = "EQH Sweep (Double Top)" if touch_count >= 2 else "HTF High Sweep"
             # print(f"DEBUG: Found {desc} at {prev_candle['time']}")
             return {
                 'swept': True, 
                 'side': 'buy_side', 
                 'level': period_high, 
                 'sweep_candle_time': prev_candle['time'],
                 'desc': desc
             }
             
        # Check Sell Side Sweep (Long Bias)
        if prev_candle['low'] < period_low and prev_candle['close'] > period_low:
             touch_count = df[df['low'] < (period_low * 1.0002)].shape[0]
             desc = "EQL Sweep (Double Bottom)" if touch_count >= 2 else "HTF Low Sweep"
             # print(f"DEBUG: Found {desc} at {prev_candle['time']}")
             return {
                 'swept': True, 
                 'side': 'sell_side', 
                 'level': period_low, 
                 'sweep_candle_time': prev_candle['time'],
                 'desc': desc
             }
             
        return {'swept': False}

    def detect_mss(self, ltf_candles: pd.DataFrame, bias_direction, sweep_time):
        current_time = ltf_candles.iloc[-1]['time']
        time_diff = (current_time - sweep_time).total_seconds() / 3600
        if time_diff > 4.0:
            return {'mss': False, 'reason': 'Expired'}

        ltf_candles = self.find_swings(ltf_candles)
        current_candle = ltf_candles.iloc[-1]
        
        if bias_direction == 'sell_side': # Long Bias
             last_swing_highs = ltf_candles[ltf_candles['is_swing_high'] == True].tail(3)
             if last_swing_highs.empty: return {'mss': False}
             
             target_swing = last_swing_highs.iloc[-1]
             if current_candle['close'] > target_swing['swing_high_val']:
                 # print(f"DEBUG: MSS Long Confirmed at {current_time} breaking {target_swing['swing_high_val']}")
                 return {
                     'mss': True, 
                     'time': current_time,
                     'level': target_swing['swing_high_val'],
                     'leg_low': ltf_candles.tail(12)['low'].min(), 
                     'leg_high': current_candle['high']
                 }

        elif bias_direction == 'buy_side': # Short Bias
             last_swing_lows = ltf_candles[ltf_candles['is_swing_low'] == True].tail(3)
             if last_swing_lows.empty: return {'mss': False}
             
             target_swing = last_swing_lows.iloc[-1]
             if current_candle['close'] < target_swing['swing_low_val']:
                 # print(f"DEBUG: MSS Short Confirmed at {current_time} breaking {target_swing['swing_low_val']}")
                 return {
                     'mss': True, 
                     'time': current_time,
                     'level': target_swing['swing_low_val'],
                     'leg_high': ltf_candles.tail(12)['high'].max(), 
                     'leg_low': current_candle['low']
                 }
                 
        return {'mss': False}

    def find_fvg(self, ltf_candles: pd.DataFrame, direction, leg_high, leg_low):
        eq_level = (leg_high + leg_low) / 2
        fvg_list = []
        
        i = len(ltf_candles) - 1
        candle_c = ltf_candles.iloc[i] 
        candle_b = ltf_candles.iloc[i-1]
        candle_a = ltf_candles.iloc[i-2]
        
        if direction == 'bullish': # Long
            if candle_a['high'] < candle_c['low']:
                gap_top = candle_c['low']
                gap_bottom = candle_a['high']
                entry_price = gap_top
                
                # print(f"DEBUG: FVG Found Bullish. Top: {gap_top}, Eq: {eq_level}")
                # Relaxed: Allow entry if price is < Eq OR within 10% of Eq?
                # Strict: gap_top < eq_level
                
                if gap_top < eq_level: # Discount
                    fvg_list.append({'top': gap_top, 'bottom': gap_bottom, 'entry': gap_top, 'type': 'bullish'})
                    
        elif direction == 'bearish': # Short
            if candle_a['low'] > candle_c['high']:
                gap_top = candle_a['low']
                gap_bottom = candle_c['high']
                entry_price = gap_bottom 
                
                # print(f"DEBUG: FVG Found Bearish. Bottom: {gap_bottom}, Eq: {eq_level}")
                
                if gap_bottom > eq_level: # Premium
                     fvg_list.append({'top': gap_top, 'bottom': gap_bottom, 'entry': gap_bottom, 'type': 'bearish'})

        return fvg_list

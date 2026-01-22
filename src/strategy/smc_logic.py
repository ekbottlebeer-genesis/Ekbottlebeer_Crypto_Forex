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
        """
        Block 2.1: HTF Liquidity Sweep Detection.
        Analyzes 1H/4H data for sweeps of PDH/PDL or EQH/EQL (50-candle lookback).
        Sweep = Price moves beyond level but candle body closes inside within 1-2 bars.
        """
        # Ensure we have enough data
        if len(htf_candles) < 55: return {'swept': False}

        # Lookback Window (excluding current forming candle)
        lookback = 50
        df = htf_candles.iloc[-(lookback+2):-1] # Recent history
        
        current_candle = htf_candles.iloc[-1]
        prev_candle = htf_candles.iloc[-2] # Potential sweep candle
        
        # 1. Identify Levels (naive approach for 50 candle High/Low)
        # Ideally we want swings, but let's use Max/Min of the window as "Major Liquidity"
        period_high = df['high'].max()
        period_low = df['low'].min()
        
        # Check Buy Side Sweep (Short Bias)
        # Condition: High > Period High AND Close < Period High
        # We check previous candle or current candle
        
        # Check Previous Candle for confirmed sweep
        if prev_candle['high'] > period_high and prev_candle['close'] < period_high:
             return {
                 'swept': True, 
                 'side': 'buy_side', # We swept highs, biased Short
                 'level': period_high, 
                 'sweep_candle_time': prev_candle['time'],
                 'desc': 'HTF High Sweep (Short Bias)'
             }
             
        # Check Sell Side Sweep (Long Bias)
        if prev_candle['low'] < period_low and prev_candle['close'] > period_low:
             return {
                 'swept': True, 
                 'side': 'sell_side', # We swept lows, biased Long
                 'level': period_low, 
                 'sweep_candle_time': prev_candle['time'],
                 'desc': 'HTF Low Sweep (Long Bias)'
             }
             
        # TODO: Implement granular EQH/EQL logic if "Max/Min" is too broad.
            
        return {'swept': False}

    def detect_mss(self, ltf_candles: pd.DataFrame, bias_direction, sweep_time):
        """
        Block 2.2: LTF Market Structure Shift (MSS).
        Returns {'mss': True, 'mss_price': float, 'displacement_high': float, 'displacement_low': float}
        expiry: Must occur within 12 candles (1 hour) of sweep_time.
        """
        # 1. Expiry Check
        current_time = ltf_candles.iloc[-1]['time']
        # Assuming timestamps are comparable (pd.Timestamp). 
        # Calculate time difference in minutes/hours or candle count if time not avail.
        # Simplified: Check if more than 1 hour has passed.
        time_diff = (current_time - sweep_time).total_seconds() / 3600
        if time_diff > 1.0:
            return {'mss': False, 'reason': 'Expired'}

        # 2. Identify Prominent Swings
        ltf_candles = self.find_swings(ltf_candles)
        
        # 3. Check for Shift
        if bias_direction == 'sell_side': # Long Bias (we swept lows)
             # Looking for Bullish MSS (Break of Swing High)
             last_swing_highs = ltf_candles[ltf_candles['is_swing_high'] == True].tail(3)
             if last_swing_highs.empty: return {'mss': False}
             
             target_swing = last_swing_highs.iloc[-1]
             
             # Current candle body close above swing high?
             current_candle = ltf_candles.iloc[-1]
             if current_candle['close'] > target_swing['swing_high_val']:
                 # Confirmed
                 # Identify Displacement Leg (Low point after sweep to Current High)
                 # Approximated: Sweep Low to Current High
                 return {
                     'mss': True, 
                     'level': target_swing['swing_high_val'],
                     'leg_low': ltf_candles.tail(12)['low'].min(), # Recent low
                     'leg_high': current_candle['high']
                 }

        elif bias_direction == 'buy_side': # Short Bias (we swept highs)
             # Looking for Bearish MSS (Break of Swing Low)
             last_swing_lows = ltf_candles[ltf_candles['is_swing_low'] == True].tail(3)
             if last_swing_lows.empty: return {'mss': False}
             
             target_swing = last_swing_lows.iloc[-1]
             
             if current_candle['close'] < target_swing['swing_low_val']:
                 return {
                     'mss': True, 
                     'level': target_swing['swing_low_val'],
                     'leg_high': ltf_candles.tail(12)['high'].max(), # Recent high
                     'leg_low': current_candle['low']
                 }
                 
        return {'mss': False}

    def find_fvg(self, ltf_candles: pd.DataFrame, direction, leg_high, leg_low):
        """
        Block 2.3: FVG & Premium/Discount Filter.
        Scans recent 3-candle sequence. Validates against 50% Fib.
        """
        # Calculate Equilibrium (50% level)
        eq_level = (leg_high + leg_low) / 2
        
        fvg_list = []
        # Check last candle pattern (Candle i is current/forming, we look at completed i-1)
        # Pattern: [i-3, i-2, i-1] -> Gap between i-3 and i-1
        
        i = len(ltf_candles) - 1
        candle_c = ltf_candles.iloc[i] # Current (or last closed)
        candle_b = ltf_candles.iloc[i-1]
        candle_a = ltf_candles.iloc[i-2]
        
        if direction == 'bullish': # Long Entry
            # Gap: High of A < Low of C
            if candle_a['high'] < candle_c['low']:
                gap_top = candle_c['low']
                gap_bottom = candle_a['high']
                entry_price = gap_top # Aggressive entry? Or top of gap? Usually Top of FVG (Discount) is entry.
                
                # Discount Filter: Must be in Discount (Lower 50% < Eq)
                if gap_top < eq_level:
                    fvg_list.append({
                        'top': gap_top,
                        'bottom': gap_bottom,
                        'entry': gap_top,
                        'type': 'bullish'
                    })
                    
        elif direction == 'bearish': # Short Entry
            # Gap: Low of A > High of C
            if candle_a['low'] > candle_c['high']:
                gap_top = candle_a['low']
                gap_bottom = candle_c['high']
                entry_price = gap_bottom 
                
                # Premium Filter: Must be in Premium (Upper 50% > Eq)
                if gap_bottom > eq_level:
                     fvg_list.append({
                        'top': gap_top,
                        'bottom': gap_bottom,
                        'entry': gap_bottom,
                        'type': 'bearish'
                    })

        return fvg_list

# src/strategy/smc_logic.py
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

class SMCLogic:
    def __init__(self):
        self.swing_lookback = 3 

    def calculate_rsi(self, series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

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
        # Must exclude the 'potentially sweeping' candles
        # Let's check the last 3 candles to see if any of them are valid sweeps
        # that have reclaimed or are reclaiming.
        
        df_base = htf_candles.iloc[:-5] # Base range for PDH/PDL
        period_high = df_base['high'].max()
        period_low = df_base['low'].min()
        
        # DEBUG PRINT START
        # print(f"DEBUG: Period High: {period_high}, Period Low: {period_low}")

        # Check last 3 candles for a sweep
        for i in range(1, 4):
            candle = htf_candles.iloc[-i]
            
            # 1. Body Close Rule & Basic Sweep Check
            # BUY SIDE SWEEP (High crosses PDH, Close < PDH)
            if candle['high'] > period_high: 
                # Check Reclaim immediately for Debugging
                is_reclaim = candle['close'] < period_high
                
                # 2. Wick Proportion Filter (>= 10% of total length)
                total_len = candle['high'] - candle['low']
                wick_len = candle['high'] - max(candle['open'], candle['close'])
                ratio = wick_len / total_len if total_len > 0 else 0
                
                if not is_reclaim:
                    # Log Breakout
                    # print(f"   [DEBUG] Candle -{i} Breakout High (Not Reclaimed). Close {candle['close']} > {period_high}")
                    pass
                
                if is_reclaim:
                    if total_len > 0 and ratio >= 0.1:
                        
                        # 3. Time-to-Reclaim Rule
                        reclaimed = False
                        # Check candles from sweep index to end
                        for j in range(-i, 0):
                            if htf_candles.iloc[j]['close'] < period_high:
                                reclaimed = True
                                break
                        
                        if reclaimed:
                            # 4. Counter-Structure Break Check
                            # Ensure no candle between sweep and current has broken the 'Extreme'
                            extreme_broken = False
                            if i > 1:
                                for k in range(-i+1, 0):
                                    if htf_candles.iloc[k]['high'] > candle['high']:
                                        extreme_broken = True
                                        break
                            
                            if not extreme_broken:
                                return {
                                    'swept': True, 
                                    'side': 'buy_side', 
                                    'level': period_high, 
                                    'extreme': candle['high'],
                                    'sweep_candle_time': candle['time'],
                                    'desc': "HTF High Sweep (Refined)"
                                }
                            else:
                                print(f"   [DEBUG] Sweep Rej: Extreme Broken (-{i})")
                        else:
                            print(f"   [DEBUG] Sweep Rej: Not Reclaimed (-{i})")
                    else:
                        print(f"   [DEBUG] Sweep Rej: Wick Too Small {ratio:.2f} < 0.1 (-{i})")

            # SELL SIDE SWEEP (Low crosses PDL, Close > PDL)
            if candle['low'] < period_low:
                is_reclaim = candle['close'] > period_low
                
                total_len = candle['high'] - candle['low']
                wick_len = min(candle['open'], candle['close']) - candle['low']
                ratio = wick_len / total_len if total_len > 0 else 0
                
                if not is_reclaim:
                   # print(f"   [DEBUG] Candle -{i} Breakout Low (Not Reclaimed). Close {candle['close']} < {period_low}")
                   pass

                if is_reclaim:
                    if total_len > 0 and ratio >= 0.1:
                        reclaimed = False
                        for j in range(-i, 0):
                            if htf_candles.iloc[j]['close'] > period_low:
                                reclaimed = True
                                break
                        
                        if reclaimed:
                            # 4. Counter-Structure Break Check
                            extreme_broken = False
                            if i > 1:
                                for k in range(-i+1, 0):
                                    if htf_candles.iloc[k]['low'] < candle['low']:
                                        extreme_broken = True
                                        break
                            
                            if not extreme_broken:
                                return {
                                    'swept': True, 
                                    'side': 'sell_side', 
                                    'level': period_low, 
                                    'extreme': candle['low'],
                                    'sweep_candle_time': candle['time'],
                                    'desc': "HTF Low Sweep (Refined)"
                                }
                            else:
                                print(f"   [DEBUG] Sweep Rej: Extreme Broken (-{i})")
                        else:
                             print(f"   [DEBUG] Sweep Rej: Not Reclaimed (-{i})")
                    else:
                        print(f"   [DEBUG] Sweep Rej: Wick Too Small {ratio:.2f} < 0.1 (-{i})")
             
        return {'swept': False, 'htf_high': period_high, 'htf_low': period_low}

    def detect_mss(self, ltf_candles: pd.DataFrame, bias_direction, sweep_time):
        current_time = ltf_candles.iloc[-1]['time']
        time_diff = (current_time - sweep_time).total_seconds() / 3600
        
        # STRICT RULE: MSS must be WITHIN 90 mins (User removed 30m min limit)
        # if time_diff < 0.5: return ... (Removed)
        
        if time_diff > 8.0:
            return {'mss': False, 'reason': 'Expired (>4h)'}

        ltf_candles = self.find_swings(ltf_candles)
        current_candle = ltf_candles.iloc[-1]
        
        if bias_direction == 'sell_side': # Long Bias
             last_swing_highs = ltf_candles[ltf_candles['is_swing_high'] == True].tail(3)
             if last_swing_highs.empty: return {'mss': False}
             
             target_swing = last_swing_highs.iloc[-1]
             target_level = target_swing['swing_high_val']
             
             if current_candle['close'] > target_level:
                 return {
                     'mss': True, 
                     'time': current_time,
                     'level': target_level,
                     'leg_low': ltf_candles.tail(12)['low'].min(), 
                     'leg_high': current_candle['high']
                 }
             else:
                 return {'mss': False, 'trigger_level': target_level, 'type': 'above'}

        elif bias_direction == 'buy_side': # Short Bias
             last_swing_lows = ltf_candles[ltf_candles['is_swing_low'] == True].tail(3)
             if last_swing_lows.empty: return {'mss': False}
             
             target_swing = last_swing_lows.iloc[-1]
             target_level = target_swing['swing_low_val']
             
             if current_candle['close'] < target_level:
                 return {
                     'mss': True, 
                     'time': current_time,
                     'level': target_level,
                     'leg_high': ltf_candles.tail(12)['high'].max(), 
                     'leg_low': current_candle['low']
                 }
             else:
                 return {'mss': False, 'trigger_level': target_level, 'type': 'below'}
                 
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
                
                # Strict: gap_top < eq_level
                
                if gap_top < eq_level: # Discount
                    fvg_list.append({'top': gap_top, 'bottom': gap_bottom, 'entry': gap_top, 'type': 'bullish'})
                    
        elif direction == 'bearish': # Short
            if candle_a['low'] > candle_c['high']:
                gap_top = candle_a['low']
                gap_bottom = candle_c['high']
                entry_price = gap_bottom 
                
                if gap_bottom > eq_level: # Premium
                     fvg_list.append({'top': gap_top, 'bottom': gap_bottom, 'entry': gap_bottom, 'type': 'bearish'})

        return fvg_list

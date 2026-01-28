import pandas as pd
import numpy as np
from src.strategy.smc_logic import SMCLogic

def test_logic():
    print("--- STARTING SMC LOGIC TEST ---")
    smc = SMCLogic()
    
    # 1. Create Dummy Data (25 candles)
    # Scenario: Range -> Sweep High -> Close Reclaim
    data = {
        'time': pd.date_range(start='2024-01-01', periods=25, freq='1H'),
        'open': [100.0] * 25,
        'high': [102.0] * 25,
        'low': [98.0] * 25,
        'close': [100.0] * 25
    }
    df = pd.DataFrame(data)
    
    # Set PDH (High of -25 to -5)
    # Candles 0-19. Let's make Candle 10 the High.
    df.at[10, 'high'] = 105.0 # Period High is 105.0
    
    # Candle -1 (Index 24): Sweep Logic
    # Case A: VALID SWEEP (High 106, Close 104, Wick > 10%)
    print("\nCase A: Testing VALID SWEEP...")
    df.at[24, 'high'] = 106.0
    df.at[24, 'close'] = 104.0 # Reclaim (< 105)
    df.at[24, 'low'] = 100.0
    # Wick = 106 - 104 = 2.0. Total = 6.0. Ratio = 33%. Valid.
    
    res = smc.detect_htf_sweeps(df)
    print(f"Result: {res}")
    
    # Case B: Wick Too Small
    print("\nCase B: Testing WICK TOO SMALL...")
    df.at[24, 'high'] = 105.1 # Just a tiny peek
    df.at[24, 'close'] = 104.9
    df.at[24, 'low'] = 100.0 
    # Wick = 0.2. Total = 5.1. Ratio = ~4%. Invalid.
    
    res = smc.detect_htf_sweeps(df)
    print(f"Result: {res}")
    
    # Case C: Not Reclaimed
    print("\nCase C: Testing NOT RECLAIMED...")
    df.at[24, 'high'] = 107.0
    df.at[24, 'close'] = 106.0 # > 105. Pivot Broken.
    res = smc.detect_htf_sweeps(df)
    print(f"Result: {res}")
    
    print("\n--- TEST COMPLETE ---")

if __name__ == "__main__":
    test_logic()

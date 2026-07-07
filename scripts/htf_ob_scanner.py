
import sys
import os
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner
import pandas as pd
import numpy as np

def scan_htf_obs():
    scanner = SMCScanner()
    symbol = "BTC/USD"
    
    for tf in ["4h", "1d", "1w"]:
        print(f"\n🧱 Scanning Bearish Resistance ({tf})...")
        df = scanner.fetch_data(symbol, tf, limit=500)
        if df is None:
            print(f"❌ Could not fetch data for {tf}")
            continue
            
        current_price = df['close'].iloc[-1]
        
        # --- 1. Detect Bearish FVGs ---
        print(f"  🔍 Checking for Bearish FVGs...")
        for i in range(2, len(df)):
            # Bearish FVG: Low of candle 1 > High of candle 3
            c1 = df.iloc[i-2]
            c3 = df.iloc[i]
            if c1['low'] > c3['high']:
                fvg_top = c1['low']
                fvg_bottom = c3['high']
                
                # Check if it has been mitigated (closed)
                future_df = df.iloc[i+1:]
                is_mitigated = not future_df.empty and future_df['high'].max() >= fvg_top
                
                if not is_mitigated and fvg_bottom > current_price:
                    print(f"  🚨 UNMITIGATED BEARISH FVG: {c1['timestamp']}")
                    print(f"     Range: ${fvg_bottom:,.2f} - ${fvg_top:,.2f}")

        # --- 2. Detect Bearish OBs ---
        print(f"  🔍 Checking for Bearish OBs...")
        highs, lows = scanner.detect_fractals(df, window=2)
        swing_high_indices = np.where(highs)[0]
        
        for idx in swing_high_indices:
            start = max(0, idx-2)
            end = min(len(df), idx+2)
            candidates = df.iloc[start:end]
            
            ob_candle = None
            for i in range(len(candidates)-1, -1, -1):
                c = candidates.iloc[i]
                if c['close'] > c['open']: # Green candle
                    ob_candle = c
                    break
            
            if ob_candle is not None:
                ob_high = ob_candle['high']
                ob_low = ob_candle['low']
                
                ob_time = ob_candle['timestamp']
                future_df = df[df['timestamp'] > ob_time]
                
                is_mitigated = not future_df.empty and future_df['high'].max() >= ob_low
                
                if not is_mitigated and ob_low > current_price:
                    print(f"  🚨 UNMITIGATED BEARISH OB: {ob_time}")
                    print(f"     Range: ${ob_low:,.2f} - ${ob_high:,.2f}")
                    print(f"     Mean Threshold: ${(ob_low + ob_high)/2:,.2f}")

if __name__ == "__main__":
    scan_htf_obs()

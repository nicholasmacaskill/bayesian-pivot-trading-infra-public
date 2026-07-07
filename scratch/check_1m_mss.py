import sys
import os
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner
import pandas as pd
import numpy as np

def check_1m_mss():
    scanner = SMCScanner()
    symbol = "BTC/USD"
    
    print(f"🕵️ Checking for 1m Structure, Double Top, Sweep, and CHoCH on {symbol}...")
    
    df = scanner.fetch_data(symbol, "1m", limit=100)
    if df is None:
        print("❌ Data fetch failed.")
        return

    # Identify Swing Highs and Lows (Window 2)
    highs, lows = scanner.detect_fractals(df, window=2)
    
    # Print recent prices and swing levels
    df['is_high'] = highs
    df['is_low'] = lows
    
    swing_high_idx = df[df['is_high']].index.tolist()
    swing_low_idx = df[df['is_low']].index.tolist()
    
    if len(swing_high_idx) < 2:
        print("Not enough swing highs to evaluate double top structure.")
        return
        
    # Get last two swing highs
    h2_idx, h1_idx = swing_high_idx[-1], swing_high_idx[-2]
    h2_price = df.loc[h2_idx, 'high']
    h1_price = df.loc[h1_idx, 'high']
    
    print(f"\nLast Swing High (H1) at index {h1_idx}: ${h1_price:.2f}")
    print(f"Current Swing High (H2) at index {h2_idx}: ${h2_price:.2f}")
    
    # Is it a double top or sweep?
    diff_pct = abs(h2_price - h1_price) / h1_price * 100
    print(f"Difference: {diff_pct:.3f}%")
    
    # Neckline (lowest point between H1 and H2)
    between_df = df.loc[h1_idx:h2_idx]
    if not between_df.empty:
        neckline_low = between_df['low'].min()
        neckline_idx = between_df['low'].idxmin()
        print(f"Neckline (lowest point between highs): ${neckline_low:.2f} at index {neckline_idx}")
    else:
        neckline_low = None
        
    current_price = df.iloc[-1]['close']
    print(f"Current Close Price: ${current_price:.2f}")
    
    if neckline_low:
        if current_price < neckline_low:
            print(f"🚨 CHoCH / MSS CONFIRMED: Current price (${current_price:.2f}) closed below the neckline (${neckline_low:.2f})!")
        else:
            print(f"⏳ NO CHoCH YET: Price has not closed below the neckline (${neckline_low:.2f}).")
            
    # Check if there is any other swing low that was recently broken
    recent_lows = df[df['is_low']]['low'].tail(4).tolist()
    if recent_lows:
        print(f"Recent swing lows: {recent_lows}")
        for l in recent_lows:
            if current_price < l:
                print(f"  - Price broke below swing low of ${l:.2f}")

if __name__ == "__main__":
    check_1m_mss()

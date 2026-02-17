
import sys
import os
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner
import pandas as pd
import numpy as np

def check_mss():
    scanner = SMCScanner()
    symbol = "BTC/USD"
    
    print(f"🕵️ Checking for Market Structure Shift (MSS) on {symbol} (5m)...")
    
    df = scanner.fetch_data(symbol, "5m", limit=50)
    if df is None:
        print("❌ Data fetch failed.")
        return

    # Identify Swing Highs and Lows (Window 2)
    highs, lows = scanner.detect_fractals(df, window=2)
    
    # Get last 2 confirmed swing lows
    swing_lows = df[lows]['low'].iloc[-4:].tolist()
    last_confirmed_low = swing_lows[-1] if swing_lows else None
    
    current_price = df.iloc[-1]['close']
    current_low = df.iloc[-1]['low']
    
    print(f"\n📊 Current Price: {current_price:.1f}")
    if last_confirmed_low:
        print(f"📉 Last Confirmed 5m Swing Low: {last_confirmed_low:.1f}")
        
        if current_price < last_confirmed_low:
            print("\n🚨 MSS DETECTED (Bearish): Price has closed below the last structural low.")
            print("💎 CONFIRMATION: The Judas Swing is likely complete (Shallow Peak).")
        else:
            print(f"\n⏳ NO MSS YET: Price needs to close below {last_confirmed_low:.1f} to confirm structural reversal.")
    
    # Check for Displacement (Candle Body Size vs ATR)
    df['body_size'] = abs(df['close'] - df['open'])
    atr = scanner.calculate_atr(df).iloc[-1]
    last_body = df['body_size'].iloc[-1]
    
    if last_body > atr * 1.2 and current_price < df.iloc[-1]['open']:
        print(f"🔥 DISPLACEMENT DETECTED: Last candle body ({last_body:.1f}) > 1.2x ATR ({atr:.1f}). Aggressive selling.")
    else:
        print(f"🟨 No significant displacement yet (Last body: {last_body:.1f}, ATR: {atr:.1f}).")

if __name__ == "__main__":
    check_mss()

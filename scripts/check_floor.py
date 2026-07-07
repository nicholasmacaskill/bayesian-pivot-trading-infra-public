import sys
import os
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner
import pandas as pd

def check_floor():
    print("🦁 Sovereign System: Scanning for Structural Floors...")
    
    scanner = SMCScanner()
    symbol = "BTC/USD"
    
    # 1. Fetch Weekly Data for Major Levels
    df_weekly = scanner.fetch_data(symbol, "1d", limit=365) # Using Daily for now as proxy for major levels
    current_price = df_weekly['close'].iloc[-1]
    
    print(f"\n💰 Current Price: {current_price:.2f}")
    
    # 2. Find Major Swing Lows (Last 6 Months)
    # Simple logic: Find local minimums in 20-day windows
    df_weekly['min_20'] = df_weekly['low'].rolling(window=20, center=True).min()
    swing_lows = df_weekly[df_weekly['low'] == df_weekly['min_20']]
    
    # Filter for lows BELOW current price
    supports = swing_lows[swing_lows['low'] < current_price].sort_values('low', ascending=False)
    
    print("\n📉 Major Structural Floors (Daily/Weekly Swings):")
    
    count = 0
    for index, row in supports.iterrows():
        if count >= 3: break
        level = row['low']
        date = row['timestamp'].strftime('%Y-%m-%d')
        dist = ((current_price - level) / current_price) * 100
        
        print(f"   ⚓️ {level:.0f}  (Swing Low from {date}) - Distance: -{dist:.1f}%")
        count += 1
        
    # 3. Psychological Levels
    print("\n🧠 Psychological Barriers:")
    for level in [65000, 60000, 50000]:
        if level < current_price:
            dist = ((current_price - level) / current_price) * 100
            print(f"   🚧 {level} - Distance: -{dist:.1f}%")

if __name__ == "__main__":
    check_floor()

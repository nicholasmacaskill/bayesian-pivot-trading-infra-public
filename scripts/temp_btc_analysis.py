
import sys
import os
import pandas as pd
from datetime import datetime, timezone

# Add project root
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner

def analyze_levels():
    scanner = SMCScanner()
    symbol = "BTC/USD"
    
    # 1. Fetch Data
    df = scanner.fetch_data(symbol, '5m', limit=100)
    if df is None:
        print("Failed to fetch data")
        return
        
    current_price = df['close'].iloc[-1]
    print(f"💎 Current BTC Price: ${current_price:,.2f}")
    
    # 2. Get Bias
    bias = scanner.get_detailed_bias(symbol)
    print(f"📊 Bias: {bias}")
    
    # 3. Find Bullish FVGs (Support Levels)
    print("\n🧐 Searching for Bullish FVGs (Support Patterns)...")
    bull_fvgs = []
    # Bullish FVG: Low(i) > High(i-2)
    for i in range(2, len(df)):
        c0 = df.iloc[i] # Current
        c1 = df.iloc[i-1] # Middle
        c2 = df.iloc[i-2] # 2 candles ago
        
        if c0['low'] > c2['high']:
            fvg_top = c0['low']
            fvg_bottom = c2['high']
            fvg_mid = (fvg_top + fvg_bottom) / 2
            # Only list FVGs below current price
            if fvg_top < current_price:
                bull_fvgs.append({
                    'top': fvg_top,
                    'bottom': fvg_bottom,
                    'mid': fvg_mid,
                    'timestamp': c0['timestamp']
                })
    
    if bull_fvgs:
        print(f"✅ Found {len(bull_fvgs)} Bullish FVGs below current price:")
        # Sort by proximity to current price
        bull_fvgs.sort(key=lambda x: x['top'], reverse=True)
        for f in bull_fvgs[:5]:
             print(f"   - ${f['top']:,.2f} to ${f['bottom']:,.2f} | Mid: ${f['mid']:,.2f} | Time: {f['timestamp']}")
    else:
        print("❌ No Bullish FVGs found on 5m timeframe.")
        
    # 4. Range Meta
    pq = scanner.get_price_quartiles(symbol)
    if pq:
        print("\n📏 Institutional Ranges:")
        if 'CBDR' in pq:
            r = pq['CBDR']
            print(f"   CBDR: Low ${r['low']:,.2f} | High ${r['high']:,.2f} | Mid: ${r['mid']:,.2f}")
        if 'London Range' in pq:
            r = pq['London Range']
            print(f"   London Range: Low ${r['low']:,.2f} | High ${r['high']:,.2f} | Mid: ${r['mid']:,.2f}")
            
    # 5. Check for Liquidity Sweeps
    print("\n🌊 Liquidity Check:")
    recent_high = df['high'].iloc[:-1].max()
    recent_low = df['low'].iloc[:-1].min()
    print(f"   Recent Session High: ${recent_high:,.2f}")
    print(f"   Recent Session Low: ${recent_low:,.2f}")
    
    if current_price > recent_high * 0.999:
        print("   ⚠️ PRICE AT HIGHS - Watch for reversal/pullback to balance.")
    elif current_price < recent_low * 1.001:
        print("   ⚠️ PRICE AT LOWS - Watch for sweep & bounce.")

if __name__ == "__main__":
    analyze_levels()

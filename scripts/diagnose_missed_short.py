import sys
import os
import pandas as pd
from datetime import datetime

sys.path.append(os.getcwd())
from src.engines.smc_scanner import SMCScanner
from src.core.config import Config

def diagnose():
    scanner = SMCScanner()
    symbol = "BTC/USD"
    
    print(f"🔍 Diagnosing Automated Scan for {symbol}...")
    
    # Bypass synchrony for diagnosis
    original_fetch = scanner.fetch_data
    def patched_fetch(*args, **kwargs):
        kwargs['synchronized'] = False
        return original_fetch(*args, **kwargs)
    scanner.fetch_data = patched_fetch
    
    df = scanner.fetch_data(symbol, "5m", limit=300)
    if df is None:
        print("❌ Could not fetch data.")
        return

    current = df.iloc[-1]
    current_price = current['close']
    
    # 1. Bias Check
    bias_full = scanner.get_detailed_bias(symbol)
    print(f"🏛️  Sovereign Bias: {bias_full}")
    
    # 2. Physics Check
    closes = df['close'].values
    hurst = scanner.get_hurst_exponent(closes)
    hurst_low, hurst_high = Config.HURST_CHAOS_RANGE
    print(f"🌀 Hurst Exponent: {hurst:.3f} (Chaos Range: {hurst_low}-{hurst_high})")
    
    # 3. Premium/Discount Check
    price_ranges = scanner.get_price_quartiles(symbol)
    if price_ranges and "Asian Range" in price_ranges:
        ar = price_ranges["Asian Range"]
        pos = (current_price - ar['low']) / (ar['high'] - ar['low'])
        print(f"📊 Asian Range: ${ar['low']:,.2f} - ${ar['high']:,.2f}")
        print(f"🎯 Current Price: ${current_price:,.2f} (Position: {pos:.2f})")
        
        min_p = Config.MIN_PRICE_QUARTILE_SHORT
        max_p = Config.MAX_PRICE_QUARTILE_SHORT
        print(f"🛡️  Short Requirement: Position must be between {min_p} and {max_p}")
        
        if pos < min_p:
            print(f"❌ REJECTED: Price is in DISCOUNT (Position {pos:.2f} < {min_p}). Selling here is low-RR according to the 98% Standard.")
        elif pos > max_p:
            print(f"❌ REJECTED: Price is extremely extended above Premium (Position {pos:.2f} > {max_p}).")
        else:
            print(f"✅ PASSED: Price is in the PREMIUM zone.")
    
    # 4. Sweep Check
    recent_high = df['high'].iloc[-288:-1].max()
    print(f"🧹 Recent 24h High (PDH): ${recent_high:,.2f}")
    if current['high'] > recent_high:
        print(f"✅ PASSED: Liquidity Sweep detected above PDH.")
    else:
        print(f"❌ REJECTED: No Liquidity Sweep of the 24h High yet. (Current high ${current['high']:,.2f} < ${recent_high:,.2f})")

if __name__ == "__main__":
    diagnose()

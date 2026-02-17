
import sys
import os
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner
import pandas as pd
import numpy as np

def analyze_macro():
    scanner = SMCScanner()
    symbol = "BTC/USD"
    
    print(f"🔭 Performing Macro Technical Audit for {symbol}...")
    
    # 1. Fetch Daily Data
    df_1d = scanner.fetch_data(symbol, "1d", limit=100)
    if df_1d is None:
        print("❌ Daily data fetch failed.")
        return

    current_price = df_1d.iloc[-1]['close']
    ath = df_1d['high'].max() # Simple ATH check in recent history
    
    print(f"\n💎 Current Price: ${current_price:,.2f}")
    print(f"🚀 All-Time High (Recent Context): ${ath:,.2f}")

    # 2. Fibonacci Extensions (from last major swing)
    # Find major swing low (last 3 months)
    swing_low = df_1d['low'].min()
    swing_high = df_1d['high'].max()
    
    diff = swing_high - swing_low
    ext_1_618 = swing_high + (diff * 0.618)
    ext_2_618 = swing_high + (diff * 1.618)
    
    print(f"\n📏 Fibonacci Extensions (Price Discovery):")
    print(f"   - 1.618 Extension: ${ext_1_618:,.2f}")
    print(f"   - Target 80k Distance: {((80000/current_price)-1)*100:.2f}%")

    # 3. Weekly Structure Check
    df_1w = scanner.fetch_data(symbol, "1w", limit=50)
    if df_1w is not None:
        # Check weekly bias
        ema20 = df_1w['close'].ewm(span=20).mean().iloc[-1]
        ema50 = df_1w['close'].ewm(span=50).mean().iloc[-1]
        weekly_bias = "BULLISH" if ema20 > ema50 else "BEARISH"
        print(f"\n📅 Weekly Bias: {weekly_bias}")
        
    print(f"\n⚖️ Macro Verdict:")
    if current_price > ath * 0.95:
        print("🌕 BULLISH OVERDRIVE: We are in striking distance of All-Time Highs.")
        print("⚠️ 80k is technically feasible if price enters Discovery Mode (Daily Close > ATH).")
    else:
        print("📉 CONSOLIDATION: Still below major macro resistance. Need ATH break first.")

if __name__ == "__main__":
    analyze_macro()

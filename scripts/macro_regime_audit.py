import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime

sys.path.append(os.getcwd())
from src.engines.smc_scanner import SMCScanner
from src.core.config import Config

def macro_audit():
    scanner = SMCScanner()
    symbol = "BTC/USD"
    
    # 1. Fetch 1D Data
    df_1d = scanner.fetch_data(symbol, "1d", limit=365, synchronized=False)
    if df_1d is None:
        print("❌ Could not fetch 1D data.")
        return

    # 2. Bias Analysis (1D)
    ema20 = df_1d['close'].ewm(span=20).mean().iloc[-1]
    ema50 = df_1d['close'].ewm(span=50).mean().iloc[-1]
    ema200 = df_1d['close'].ewm(span=200).mean().iloc[-1]
    
    current_price = df_1d['close'].iloc[-1]
    
    print(f"🏛️  1D Bias Analysis:")
    print(f"   • Current Price: ${current_price:,.2f}")
    print(f"   • EMA 20:        ${ema20:,.2f} ({'Above' if current_price > ema20 else 'Below'})")
    print(f"   • EMA 50:        ${ema50:,.2f} ({'Above' if current_price > ema50 else 'Below'})")
    print(f"   • EMA 200:       ${ema200:,.2f} ({'Above' if current_price > ema200 else 'Below'})")
    
    # 3. Market Structure (1D)
    is_high, is_low = scanner.detect_fractals(df_1d, window=5)
    swing_highs = df_1d[is_high]['high']
    swing_lows = df_1d[is_low]['low']
    
    last_h = swing_highs.iloc[-1]
    last_l = swing_lows.iloc[-1]
    prev_h = swing_highs.iloc[-2]
    prev_l = swing_lows.iloc[-2]
    
    structure = "CONSOLIDATION"
    if last_h < prev_h and last_l < prev_l:
        structure = "BEARISH (Lower Highs & Lower Lows)"
    elif last_h > prev_h and last_l > prev_l:
        structure = "BULLISH (Higher Highs & Higher Lows)"
    
    print(f"\n🏛️  1D Market Structure: {structure}")
    print(f"   • Last Swing High: ${last_h:,.2f}")
    print(f"   • Last Swing Low:  ${last_l:,.2f}")
    
    # 4. CHoCH Analysis
    print(f"\n🏛️  CHoCH Watch (1D):")
    if current_price < last_l:
        print(f"   🚨 BEARISH CHoCH: Price broken below last 1D Swing Low.")
    elif current_price > last_h:
        print(f"   🚀 BULLISH CHoCH: Price broken above last 1D Swing High.")
    else:
        print(f"   ⏳ NO CHoCH: Price range-bound between ${last_l:,.2f} and ${last_h:,.2f}")

    # 5. Conclusion
    print("\n⚖️  FINAL MACRO VERDICT:")
    if current_price < ema200:
        print("   🔴 DEEP BEAR MARKET: Price below 200-day EMA.")
    elif structure == "BEARISH (Lower Highs & Lower Lows)":
        print("   🔴 MACRO CORRECTION: Market structure is trending down.")
    else:
        print("   🟡 TRANSITION/CONSOLIDATION: Awaiting structural shift.")

if __name__ == "__main__":
    macro_audit()

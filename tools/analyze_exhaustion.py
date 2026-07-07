import sys
import os
import pandas as pd
import numpy as np

# Add project root to path
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner

def analyze_trend_exhaustion():
    print("🧠 Analyzing Trend Exhaustion Markers for BTC/USD...")
    scanner = SMCScanner()
    
    # 1. Check Hurst Exponent (Trend vs Mean Reversion)
    df_1h = scanner.fetch_data("BTC/USD", '1h', limit=100)
    if df_1h is None: return
    
    hurst = scanner.get_hurst_exponent(df_1h['close'].values)
    print(f"📈 Hurst Exponent (1H): {hurst:.2f}")
    if hurst > 0.6:
        print("   ✅ Conclusion: Strong Trending Regime. Reversal likely some time out.")
    elif 0.45 <= hurst <= 0.55:
        print("   ⚠️ Conclusion: Random Walk / Rejection Zone. Trend is stalling.")
    elif hurst < 0.45:
        print("   🚨 Conclusion: Mean Reverting. High probability of Trend Exhaustion / Range.")

    # 2. RSI Over-extension (Exhaustion)
    rsi = scanner.calculate_rsi(df_1h).iloc[-1]
    print(f"📊 RSI (1H): {rsi:.2f}")
    if rsi > 70 or rsi < 30:
        print(f"   🚨 Conclusion: Over-extended. Be cautious with momentum trades.")

    # 3. Market Structure Multi-Timeframe (MTF)
    print("\n🔍 MTF Structure Check:")
    df_4h = scanner.fetch_data("BTC/USD", '4h', limit=50)
    df_15m = scanner.fetch_data("BTC/USD", '15m', limit=50)
    
    # 4H Structure
    h4_bias = scanner.get_detailed_bias("BTC/USD")
    print(f"   [4H]: {h4_bias}")
    
    # 15m Structure (the early warning)
    m15_highs = (df_15m['high'] > df_15m['high'].shift(1)) & (df_15m['high'] > df_15m['high'].shift(-1))
    m15_lows = (df_15m['low'] < df_15m['low'].shift(1)) & (df_15m['low'] < df_15m['low'].shift(-1))
    
    last_15m_high = df_15m[m15_highs]['high'].iloc[-1]
    last_15m_low = df_15m[m15_lows]['low'].iloc[-1]
    curr_price = df_15m['close'].iloc[-1]
    
    print(f"   [15m]: Current Price: ${curr_price:,.0f} | Range: ${last_15m_low:,.0f} - ${last_15m_high:,.0f}")
    
    if curr_price > last_15m_high:
        print("   🚀 15m Structure is currently BULLISH (Expansion).")
    elif curr_price < last_15m_low:
        print("   📉 15m Structure is currently BEARISH (Expansion).")
    else:
        print("   ⚖️ 15m Structure is CONSOLIDATING.")

if __name__ == "__main__":
    analyze_trend_exhaustion()

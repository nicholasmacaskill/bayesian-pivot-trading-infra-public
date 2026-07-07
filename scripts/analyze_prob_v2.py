import sys
import os
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner
import pandas as pd
import numpy as np

def analyze_sl_vs_tp_probability():
    print("🦁 Sovereign System: SL vs TP Probability Audit...")
    
    scanner = SMCScanner()
    symbol = "BTC/USD"
    
    # 0. Fetch Latest Data
    df = scanner.fetch_data(symbol, "1h", limit=100)
    current_price = df['close'].iloc[-1]
    
    # Trade Specs (Open Long Position)
    entry = 63717.88
    sl = 62384.54
    tp = 69451.21
    
    # 1. Distances
    dist_to_sl = current_price - sl
    dist_to_tp = tp - current_price
    
    pct_to_sl = (dist_to_sl / current_price) * 100
    pct_to_tp = (dist_to_tp / current_price) * 100
    
    # 2. Market Bias
    bias = scanner.get_detailed_bias(symbol)
    
    # 3. Volatility (1H ATR for intraday/short term)
    atr = scanner.calculate_atr(df, period=14).iloc[-1]
    
    # 4. Immediate Structural Barriers
    # SSL Magnet from previous scans: $63,019.60
    ssl_magnet = 63019.60
    
    print(f"\n💎 Current Price: ${current_price:,.2f}")
    print(f"🛑 Stop Loss:    ${sl:,.2f} (-{pct_to_sl:.2f}%)")
    print(f"🎯 Take Profit:  ${tp:,.2f} (+{pct_to_tp:.2f}%)")
    print(f"📊 1H ATR:        ${atr:,.2f}")
    print(f"🧭 Trend Bias:    {bias}")
    print(f"🧲 Immediate SSL: ${ssl_magnet:,.2f}")

    # 5. Probabilistic Calculation
    # Simple model: Distance weighted by Bias and Structure
    
    # Pure distance probability (ignoring trend)
    # The closer it is, the more likely.
    total_dist = dist_to_sl + dist_to_tp
    base_sl_prob = (1 - (dist_to_sl / total_dist)) * 100
    base_tp_prob = (1 - (dist_to_tp / total_dist)) * 100
    
    # Adjustment for Bias
    bias_adj = 0
    if "STRONG BEARISH" in bias: bias_adj = 30 # Heavy skew toward down
    elif "BEARISH" in bias: bias_adj = 15
    elif "BULLISH" in bias: bias_adj = -15
    
    # Adjustment for Structure (Magnet)
    struc_adj = 0
    if current_price > ssl_magnet > sl:
        struc_adj = 10 # Magnet is on the way to SL
        
    final_sl_prob = base_sl_prob + bias_adj + struc_adj
    final_tp_prob = 100 - final_sl_prob
    
    # Clamp
    final_sl_prob = max(5, min(95, final_sl_prob))
    final_tp_prob = 100 - final_sl_prob
    
    print("\n🎲 SYSTEM PROBABILITY FORECAST:")
    print(f"🔴 Chance of hitting STOP LOSS:    {final_sl_prob:.1f}%")
    print(f"🟢 Chance of hitting TAKE PROFIT:  {final_tp_prob:.1f}%")
    
    if "BEARISH" in bias and final_sl_prob > 70:
        print("\n⚠️  ADVISORY: Negative Expected Value (EV). Trade is positioned in front of a Bearish Expansion.")
    elif final_tp_prob > 60:
        print("\n✅ ADVISORY: Positive Skew. Strategy alignment is favorable.")

if __name__ == "__main__":
    analyze_sl_vs_tp_probability()

import sys
import os
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner
import pandas as pd
import numpy as np

def calculate_probability():
    print("🦁 Sovereign System: Calculating 65k Probability...")
    
    scanner = SMCScanner()
    symbol = "BTC/USD"
    target = 65000
    
    # 1. Fetch Daily Data for ATR/Volatility
    df_daily = scanner.fetch_data(symbol, "1d", limit=30)
    current_price = df_daily['close'].iloc[-1]
    
    # 2. Calculate Distance
    distance = current_price - target
    pct_distance = (distance / current_price) * 100
    
    print(f"\n💰 Current: {current_price:.2f}")
    print(f"🎯 Target:  {target:.0f}")
    print(f"📉 Distance: -{distance:.2f} (-{pct_distance:.2f}%)")
    
    # 3. Calculate Volatility (ATR)
    atr = scanner.calculate_atr(df_daily, period=14).iloc[-1]
    print(f"📊 Daily ATR (Volatility): {atr:.2f} (~{(atr/current_price)*100:.2f}%)")
    
    # 4. Statistical Likelihood (Z-Score approximation)
    # How many "Days" of volatility is this move?
    days_to_target = distance / atr
    print(f"⏳ implied Time: Move requires ~{days_to_target:.1f} days of full volatility.")
    
    # 5. Trend Bias
    bias = scanner.get_detailed_bias(symbol, visual_check=False)
    print(f"🧭 Trend Bias: {bias}")
    
    # 6. Support Levels (Asian/London)
    quartiles = scanner.get_price_quartiles(symbol)
    supports_broken = 0
    barriers = []
    
    if quartiles:
        # Check Asian Low
        al = quartiles['Asian Range']['low']
        if current_price > al > target:
            barriers.append(f"Asian Low ({al:.0f})")
        
        # Check CBDR Low (if available)
        if 'CBDR' in quartiles:
            cl = quartiles['CBDR']['low']
            if current_price > cl > target:
                 barriers.append(f"CBDR Low ({cl:.0f})")

    # 7. Final Verdict
    print("\n🎲 SYSTEM PROBABILITY:")
    
    prob_score = 50 # Base
    
    # Trend Bonus
    if "STRONG BEARISH" in bias: prob_score += 25
    elif "BEARISH" in bias: prob_score += 15
    elif "BULLISH" in bias: prob_score -= 20
    
    # Distance Penalty (Harder if further away)
    if pct_distance > 5: prob_score -= 20
    elif pct_distance > 3: prob_score -= 10
    
    # Barrier Penalty
    prob_score -= (len(barriers) * 5)
    
    print(f"   Estimated Probability: {prob_score}%")
    
    if barriers:
        print(f"   ⚠️ Major Obstacles: {', '.join(barriers)}")
    else:
        print("   ✅ Path Clear of Session Structure.")

if __name__ == "__main__":
    calculate_probability()

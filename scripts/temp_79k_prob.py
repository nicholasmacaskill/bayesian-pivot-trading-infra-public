
import sys
import os
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner
import pandas as pd
import numpy as np

def calculate_probability(target=79000):
    print(f"🦁 Sovereign System: Calculating {target/1000:.0f}k Probability by THIS TIME TOMORROW...")
    
    scanner = SMCScanner()
    symbol = "BTC/USD"
    
    # 1. Fetch Daily Data for ATR/Volatility
    df_daily = scanner.fetch_data(symbol, "1d", limit=30)
    current_price = df_daily['close'].iloc[-1]
    
    # 2. Calculate Distance
    distance = target - current_price
    pct_distance = (distance / current_price) * 100
    
    # 3. Time Component (24 Hours)
    hours_left = 24
    
    print(f"\n💰 Current: {current_price:.2f}")
    print(f"🎯 Target:  {target:.0f}")
    print(f"📈 Distance: +{distance:.2f} (+{pct_distance:.2f}%)")
    print(f"⏰ Time Horizon: 24 Hours")
    
    # 4. Calculate Volatility (ATR)
    atr = scanner.calculate_atr(df_daily, period=14).iloc[-1]
    print(f"📊 Daily ATR (Volatility): {atr:.2f} (~{(atr/current_price)*100:.2f}%)")
    
    # Statistical Reality Check
    # How many ATRs is this move?
    atr_multiple = distance / atr
    
    # Required velocity in USD/hr
    required_velocity = distance / hours_left
    avg_velocity = atr / 24
    
    print(f"🚀 Required Velocity: ${required_velocity:.2f}/hr")
    print(f"🐢 Average Velocity: ${avg_velocity:.2f}/hr")
    print(f"📏 Distance in ATRs: {atr_multiple:.2f}x Daily Move")
    
    # 5. Trend Bias
    bias = scanner.get_detailed_bias(symbol, visual_check=False)
    print(f"🧭 Trend Bias: {bias}")
    
    # 6. Obstacles
    quartiles = scanner.get_price_quartiles(symbol)
    barriers = []
    
    if quartiles:
        # Check Today High
        if 'CBDR' in quartiles:
            th = quartiles['CBDR']['high']
            if current_price < th < target:
                barriers.append(f"Previous High ({th:.0f})")

    # 7. Final Verdict
    print(f"\n🎲 SYSTEM PROBABILITY ({target/1000:.0f}k in 24H):")
    
    # Math: 
    # 1 ATR move in 24h = ~68% probability (within 1 SD area, but directional)
    # Logistically:
    if atr_multiple > 3:
        prob_score = 10
    elif atr_multiple > 2:
        prob_score = 20
    elif atr_multiple > 1.5:
        prob_score = 35
    elif atr_multiple > 1:
        prob_score = 55
    else:
        prob_score = 75
        
    # Bias Adjustment
    if "STRONG BULLISH" in bias: prob_score += 15
    elif "BULLISH" in bias: prob_score += 10
    elif "BEARISH" in bias: prob_score -= 10
    
    # Momentum Bonus (Hurst)
    closes = df_daily['close'].values
    hurst = scanner.get_hurst_exponent(closes)
    if hurst > 0.5:
         print(f"🔥 Momentum Detected (Hurst {hurst:.2f})")
         prob_score += 10

    print(f"   Estimated Probability: {prob_score}%")
    print(f"   Confidence Level: {'HIGH' if prob_score > 60 else 'MODERATE' if prob_score > 30 else 'LOW'}")
    
    if barriers:
        print(f"   ⚠️ Resistance Barriers: {', '.join(barriers)}")

if __name__ == "__main__":
    calculate_probability(79000)

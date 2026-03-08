
import sys
import os
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner
import pandas as pd

def get_current_play():
    print("🦁 Sovereign Analysis: Real-time Playbook for BTC/USD...")
    
    scanner = SMCScanner()
    symbol = "BTC/USD"
    
    # 1. Get Contextual Bias
    index_context = scanner.intermarket.get_market_context()
    bias = scanner.get_detailed_bias(symbol, index_context=index_context, visual_check=False)
    
    # 2. Fetch High-Res Data (5m) for current pullback analysis
    df = scanner.fetch_data(symbol, "5m", limit=100)
    current_price = df['close'].iloc[-1]
    
    # 3. Identify nearest Liquidity/Support mapping
    # Look for Order Block or FVG in the current pullback range
    ob = scanner.find_order_block(df, len(df)-20, 'LONG')
    
    print(f"\n💰 Current Price: ${current_price:.2f}")
    print(f"🧭 Sovereign Bias: {bias}")
    
    # 4. SMT Divergence check
    smt_type, smt_strength = scanner.intermarket.detect_true_smt(df, "DXY")
    if smt_type:
        print(f"⚡ SMT Detected: {smt_type} (Strength: {smt_strength})")
    else:
        print("⚡ SMT: None Detected.")

    # 5. Price Quartile mapping
    quartiles = scanner.get_price_quartiles(symbol)
    
    # 6. Recommendation logic based on ICT/Bayesian principles
    print("\n📝 STRATEGIC PLAY:")
    
    # Level-based assessment
    pullback_target = 73350 # Previous identified support
    if current_price <= pullback_target + 50:
         print(f"🟢 ENTRY ZONE: Price is currently at/near the identified support level (${pullback_target}).")
         print("   Action: Look for a 5m Market Structure Shift (MSS) as entry confirmation.")
    else:
         print(f"🟡 WAITING: Price is hovering. Ideally wait for a deeper retest of ${pullback_target} or a break of the Asian high.")

    # Risk Check
    if "BEARISH" in bias:
        print("🔴 CAUTION: Bias has shifted Bearish. Longs are counter-trend right now.")
    elif "NEUTRAL" in bias:
        print("🟡 CAUTION: Market is in a range (Accumulation). Expect chop until the London open.")
    
    print(f"\n🏁 VERDICT:")
    if "BULLISH" in bias and current_price < 73500:
        print("   PLAY: SCALE-IN LONG.")
        print("   Invalidation: Close below $72,500.")
        print("   Target 1: $74,100 (Session High)")
        print("   Target 2: $79,000 (24h Momentum Target)")
    else:
        print("   PLAY: OBSERVE. Position size should be reduced or wait for volatility expansion.")

if __name__ == "__main__":
    get_current_play()

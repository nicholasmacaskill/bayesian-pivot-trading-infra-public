import sys
import os
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner
import pandas as pd

def check_lag():
    print("🦁 Sovereign System: Analyzing BTC vs SOL Lag...")
    
    scanner = SMCScanner()
    
    # Fetch last 4 hours of 5m data
    df_btc = scanner.fetch_data("BTC/USD", "5m", limit=48)
    df_sol = scanner.fetch_data("SOL/USD", "5m", limit=48)
    
    if df_btc is None or df_sol is None:
        print("❌ Error fetching data.")
        return

    # Calculate % drop from high of session
    btc_high = df_btc['high'].max()
    btc_curr = df_btc['close'].iloc[-1]
    btc_drop = ((btc_curr - btc_high) / btc_high) * 100
    
    sol_high = df_sol['high'].max()
    sol_curr = df_sol['close'].iloc[-1]
    sol_drop = ((sol_curr - sol_high) / sol_high) * 100
    
    print(f"\n📉 4H Drop Performance:")
    print(f"   BTC: {btc_drop:.2f}%")
    print(f"   SOL: {sol_drop:.2f}%")
    
    diff = sol_drop - btc_drop
    print(f"\n📊 Divergence: {diff:.2f}%")
    
    if diff > 0.5:
        print("   ✅ OPPORTUNITY: SOL has NOT dropped as much as BTC yet.")
        print("      It is 'lagging' and may play catch-up.")
    elif diff < -0.5:
        print("   ⚠️ SOL is weaker than BTC (Led the drop). No lag edge.")
    else:
        print("   ⚠️ Moves are identical. No clear lag edge.")

if __name__ == "__main__":
    check_lag()

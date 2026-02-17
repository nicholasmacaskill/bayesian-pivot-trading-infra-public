
import sys
import os
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner
import pandas as pd
from datetime import datetime

def estimate_timing():
    scanner = SMCScanner()
    symbol = "BTC/USD"
    target = 75000
    
    # Get 1D data for ATR
    df_daily = scanner.fetch_data(symbol, "1d", limit=30)
    if df_daily is None:
        print("Data fetch failed.")
        return
        
    current_price = df_daily['close'].iloc[-1]
    dist_to_target = target - current_price
    
    # Calculate ATR
    df_daily['tr'] = df_daily.apply(lambda x: max(x['high'] - x['low'], abs(x['high'] - x['close']), abs(x['low'] - x['close'])), axis=1)
    atr = df_daily['tr'].tail(14).mean()
    
    # Calculate average positive daily move (momentum)
    df_daily['change'] = df_daily['close'].diff()
    avg_pos_move = df_daily[df_daily['change'] > 0]['change'].tail(7).mean()
    
    print(f"💰 Current Price: ${current_price:,.2f}")
    print(f"🎯 Target Price: ${target:,.2f}")
    print(f"📏 Distance: ${dist_to_target:,.2f}")
    print(f"📉 Daily ATR: ${atr:,.2f}")
    print(f"🚀 Avg Positive Daily Move (last 7 green days): ${avg_pos_move:,.2f}")
    
    if dist_to_target <= 0:
        print("Target already hit!")
        return

    days_to_target_atr = dist_to_target / atr
    days_to_target_mom = dist_to_target / avg_pos_move
    
    print(f"\n⏳ Estimated Time to Hit:")
    print(f"   - Conservative (ATR-based): {days_to_target_atr:.1f} days")
    print(f"   - Aggressive (Momentum-based): {days_to_target_mom:.1f} days")

if __name__ == "__main__":
    estimate_timing()

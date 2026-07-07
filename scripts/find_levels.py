
import sys
import os
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner
from src.core.config import Config
import pandas as pd

def find_resistance_levels():
    scanner = SMCScanner()
    symbol = "BTC/USD"
    
    print(f"🔍 Determining Tactical Levels for {symbol}...")
    
    # 1. Fetch Data
    df_15m = scanner.fetch_data(symbol, "15m", limit=100)
    df_1h = scanner.fetch_data(symbol, "1h", limit=100)
    
    if df_15m is None or df_1h is None:
        print("❌ Error fetching data.")
        return

    current_price = df_15m.iloc[-1]['close']
    print(f"💰 Current Price: {current_price:.1f}")

    # 2. Find Bearish FVGs above current price
    def find_bearish_fvgs(df):
        fvgs = []
        for i in range(2, len(df)):
            c0 = df.iloc[i]     # Current
            c2 = df.iloc[i-2]   # 2 candles ago
            
            # Bearish FVG: Low of candle i-2 > High of candle i
            if c2['low'] > c0['high']:
                fvg_top = c2['low']
                fvg_bottom = c0['high']
                # Check if above current price and unmitigated by intermediate candles
                if fvg_bottom > current_price:
                    # Simple mitigation check: has any candle since i closed above fvg_bottom?
                    mitigated = df.iloc[i+1:]['high'].max() > fvg_bottom if i + 1 < len(df) else False
                    if not mitigated:
                        fvgs.append({'top': fvg_top, 'bottom': fvg_bottom})
        return fvgs

    fvgs_15m = find_bearish_fvgs(df_15m)
    fvgs_1h = find_bearish_fvgs(df_1h)

    print("\n🛑 Bearish FVGs (Resistance):")
    for fvg in fvgs_15m[:3]:
        print(f"   [15m] {fvg['bottom']:.1f} - {fvg['top']:.1f}")
    for fvg in fvgs_1h[:2]:
        print(f"   [1h]  {fvg['bottom']:.1f} - {fvg['top']:.1f}")

    # 3. Session Highs (Judas Targets)
    pq = scanner.get_price_quartiles(symbol)
    if pq:
        print("\n🎯 Judas Sweep Targets (Session Highs/SDs):")
        for name, r in pq.items():
            print(f"   {name}: High {r['high']:.1f} | SD+1 {r['sd_1_pos']:.1f}")

    # 4. Stop Loss Calculation
    atr = scanner.calculate_atr(df_1h).iloc[-1]
    sl_aggressive = current_price + (atr * 1.5)
    sl_defensive = current_price + (atr * 2.5)
    
    # Higher Timeframe Swing High (Structural Invalidation)
    swing_high = df_1h['high'].iloc[-50:].max()
    
    print("\n🛡️ SL Recommendations:")
    print(f"   Aggressive (1.5 ATR): {sl_aggressive:.1f}")
    print(f"   Defensive (2.5 ATR):  {sl_defensive:.1f}")
    print(f"   Structural Invalidation (Recent 1H High): {swing_high:.1f}")

if __name__ == "__main__":
    find_resistance_levels()

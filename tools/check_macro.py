from src.engines.smc_scanner import SMCScanner
import pandas as pd

def check_macro_context():
    scanner = SMCScanner()
    symbol = "BTC/USD"
    
    print(f"🔍 Analyzing MACRO Context for {symbol}...")
    
    try:
        # Fetch 300 Daily candles (~1 year)
        df_1d = scanner.exchange.fetch_ohlcv(symbol, timeframe='1d', limit=300)
    except Exception as e:
        print(f"Error fetching data: {e}")
        return
        
    current_price = df_1d[-1][4]
    
    print(f"💎 Current Price: ${current_price:,.2f}")
    
    # 1. Macro Range and Discount
    macro_low = min([d[3] for d in df_1d])
    macro_high = max([d[2] for d in df_1d])
    retracement_level = macro_low + 0.5 * (macro_high - macro_low)
    
    print(f"\n--- Macro Structure (Last 300 Days) ---")
    print(f"🌊 Range: ${macro_low:,.2f} - ${macro_high:,.2f}")
    if current_price < retracement_level:
        print(f"✅ Price is in DISCOUNT (Below Equilibrium: ${retracement_level:,.2f})")
    else:
        print(f"⚠️ Price is in PREMIUM (Above Equilibrium: ${retracement_level:,.2f})")

    # 2. Check for Weekly Lows (using Daily data to approx)
    # Group into weeks
    print("\n--- Recent Swing Points ---")
    # Last 30 days low
    low_30d = min([d[3] for d in df_1d[-30:]])
    print(f"📉 30-Day Low: ${low_30d:,.2f}")
    
    if abs(current_price - low_30d) / current_price < 0.05:
         print("📍 We are trading near the monthly lows.")
    else:
         print("🚀 We are significantly above the monthly lows.")

    # 3. Volume Trend
    print("\n--- Volume Analysis ---")
    # Compare last 3 days volume vs 30 day average
    recent_vol = sum([d[5] for d in df_1d[-3:]]) / 3
    avg_vol = sum([d[5] for d in df_1d[-30:]]) / 30
    
    vol_ratio = recent_vol / avg_vol
    print(f"📊 Recent Volume Ratio: {vol_ratio:.2f}x vs 30-Day Avg")
    
    if vol_ratio > 1.2:
         print("✅ Volume is expanding (Sign of potential reversal/breakout).")
    elif vol_ratio < 0.8:
         print("⚠️ Volume is contracting (Consolidation).")
    else:
         print("Running at average volume.")

if __name__ == "__main__":
    check_macro_context()

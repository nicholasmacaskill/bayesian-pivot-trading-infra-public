from src.engines.smc_scanner import SMCScanner
import pandas as pd

def check_range_liquidity():
    scanner = SMCScanner()
    symbol = "BTC/USD"
    
    print(f"🔍 Analyzing the gap between $65,800 and $60,000 for {symbol}...")
    
    # Use 1h for more detail and 1d for major levels
    try:
        df_1d = scanner.exchange.fetch_ohlcv(symbol, timeframe='1d', limit=50)
        df_1h = scanner.exchange.fetch_ohlcv(symbol, timeframe='1h', limit=300)
    except Exception as e:
        print(f"Error fetching data: {e}")
        return
    
    print("\n--- Higher Timeframe (1D) Intermediate Levels ---")
    for d in df_1d:
        price_l = d[3]
        price_h = d[2]
        if 60000 <= price_l <= 65800:
            print(f"📍 Daily Low at ${price_l:,.2f} ({pd.to_datetime(d[0], unit='ms').strftime('%Y-%m-%d')})")
        if 60000 <= price_h <= 65800:
            print(f"📍 Daily High at ${price_h:,.2f} ({pd.to_datetime(d[0], unit='ms').strftime('%Y-%m-%d')})")

    print("\n--- 1H Efficiency (Fair Value Gaps) ---")
    gaps = []
    for i in range(2, len(df_1h)):
        # Bullish FVG: Low[i] > High[i-2]
        if df_1h[i][3] > df_1h[i-2][2]:
            top = df_1h[i][3]
            bottom = df_1h[i-2][2]
            if top > 60000 and bottom < 65800:
                gaps.append((bottom, top))
    
    if gaps:
        # Sort and filter for distinct zones
        gaps.sort(key=lambda x: x[0], reverse=True)
        for b, t in gaps[:5]: # Show top 5 nearest ones
            print(f"🛡️ 1H Bullish FVG (Support Zone): ${b:,.2f} - ${t:,.2f}")
    else:
        print("⚠️ No Bullish FVGs found between 60k and 65.8k.")

    # Check for Volume Profile "Value Area" or "HVN" - (Simplified check: looking for price clusters)
    prices = [d[4] for d in df_1h]
    in_range = [p for p in prices if 62500 <= p <= 64500]
    if len(in_range) > 20:
        print(f"📦 Volume Cluster detected around 63.5k (Intermediate Support).")

if __name__ == "__main__":
    check_range_liquidity()

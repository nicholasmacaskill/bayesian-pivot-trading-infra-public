import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

def check_outcome(symbol, timestamp_str, direction, entry_price, sl_price, tp_price):
    print(f"\n📊 Verifying Outcome for {symbol} at {timestamp_str}...")
    print(f"   Entry: {entry_price:.2f} | SL: {sl_price:.2f} | TP: {tp_price:.2f}")

    # Map symbol for yfinance
    yf_sym = symbol.replace("/", "-")
    
    # Parse timestamp and make it UTC-aware to match yfinance
    import pytz
    ts = datetime.fromisoformat(timestamp_str.split(".")[0]).replace(tzinfo=pytz.UTC)
    
    # Fetch 48 hours of data after the timestamp
    start_str = ts.strftime('%Y-%m-%d')
    end_str = (ts + timedelta(days=3)).strftime('%Y-%m-%d')
    
    df = yf.download(yf_sym, start=start_str, end=end_str, interval='5m', progress=False)
    if df.empty:
        print("   ❌ No price data found.")
        return "Unknown"

    # Filter for data starting AFTER the scan timestamp
    df = df[df.index >= ts]
    
    # Simulate trade
    for idx, row in df.iterrows():
        # Handle multi-index if necessary (Ticker name as top level)
        if isinstance(row.index, pd.MultiIndex):
            low = float(row[('Low', yf_sym)])
            high = float(row[('High', yf_sym)])
        else:
            low = float(row['Low'])
            high = float(row['High'])
        
        if direction == 'LONG':
            if low <= sl_price:
                print(f"   🛑 STOP LOSS HIT at {idx}")
                return "LOSS"
            if high >= tp_price:
                print(f"   🎯 TARGET HIT at {idx}")
                return "WIN"
        else: # SHORT
            if high >= sl_price:
                print(f"   🛑 STOP LOSS HIT at {idx}")
                return "LOSS"
            if low <= tp_price:
                print(f"   🎯 TARGET HIT at {idx}")
                return "WIN"
                
    print("   ⏳ Trade still open or no conclusion in data window.")
    return "OPEN"

def benchmark_missed():
    # 1. BTC/USD Bullish Order Block (Feb 13, 23:20)
    # Price was around $68,860
    check_outcome("BTC/USD", "2026-02-13T23:20:00", "LONG", 68860, 68400, 70500)

    # 2. SOL/USD Bearish Trend Pullback (Feb 13, 03:49)
    # Price was around $150
    check_outcome("SOL/USD", "2026-02-13T03:49:00", "SHORT", 150, 153, 142)

    # 3. BTC/USD Bearish Order Block (Feb 13, 04:30)
    # Price was around $66,300
    check_outcome("BTC/USD", "2026-02-13T04:30:00", "SHORT", 66300, 67000, 65000)

if __name__ == "__main__":
    benchmark_missed()

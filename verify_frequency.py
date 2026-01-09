import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def fetch_data(symbol, days=30):
    print(f"📥 Fetching {symbol} data for last {days} days...")
    exchange = ccxt.binance({'enableRateLimit': True})
    
    since = exchange.parse8601((datetime.utcnow() - timedelta(days=days)).isoformat())
    all_data = []
    
    while True:
        ohlcv = exchange.fetch_ohlcv(symbol, '5m', since=since, limit=1000)
        if not ohlcv: break
        since = ohlcv[-1][0] + 1
        all_data.extend(ohlcv)
        if since > datetime.utcnow().timestamp() * 1000: break
        
    df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def scan_hybrid_sweeps(df):
    setups = 0
    df = df.copy()
    
    # Pre-calculate rolling 24h High/Low (288 periods)
    df['pdh'] = df['high'].rolling(288).max().shift(1)
    df['pdl'] = df['low'].rolling(288).min().shift(1)
    
    # Calculate London High/Low (approximate for speed: max/min of 7-10 UTC window)
    # We will compute this row by row for accuracy in the loop or vectorized
    
    print("🔄 Scanning for Hybrid Sweeps...")
    
    for i in range(288, len(df)):
        row = df.iloc[i]
        
        # 1. Check Time (NY Session Only: 12-20 UTC)
        if not (12 <= row['timestamp'].hour < 20):
            continue
            
        # 2. Check PDH Sweep (Bearish)
        # Sweep High but Close Low
        pdh = df.iloc[i-1]['pdh']
        swept_pdh = row['high'] > pdh and row['close'] < pdh
        
        # 3. Check London Sweep (Bearish)
        # Get London High (7-10 UTC) for THIS day
        current_day = row['timestamp'].date()
        # Filter mostly correct rows
        london_rows = df[
            (df['timestamp'].dt.date == current_day) & 
            (df['timestamp'].dt.hour >= 7) & 
            (df['timestamp'].dt.hour < 10)
        ]
        
        swept_london = False
        if not london_rows.empty:
            london_high = london_rows['high'].max()
            swept_london = row['high'] > london_high and row['close'] < london_high
            
        # BEARISH SETUP
        if swept_pdh or swept_london:
            setups += 1
            
        # 4. Check PDL Sweep (Bullish)
        pdl = df.iloc[i-1]['pdl']
        swept_pdl = row['low'] < pdl and row['close'] > pdl
        
        swept_london_low = False
        if not london_rows.empty:
            london_low = london_rows['low'].min()
            swept_london_low = row['low'] < london_low and row['close'] > london_low
            
        # BULLISH SETUP
        if swept_pdl or swept_london_low:
            setups += 1
            
    return setups

if __name__ == "__main__":
    btc_df = fetch_data('BTC/USDT', days=30)
    eth_df = fetch_data('ETH/USDT', days=30)
    
    btc_setups = scan_hybrid_sweeps(btc_df)
    eth_setups = scan_hybrid_sweeps(eth_df)
    
    total = btc_setups + eth_setups
    print("\n" + "="*50)
    print("📊 HYBRID LOGIC FREQUENCY TEST (Last 30 Days)")
    print("="*50)
    print(f"BTC Setups: {btc_setups}")
    print(f"ETH Setups: {eth_setups}")
    print(f"Total Monthly: {total}")
    print(f"Projected Yearly: {total * 12}")
    print(f"Avg Daily Setups: {total / 30:.1f}")
    print("="*50)

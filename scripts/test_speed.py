import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os
import time

sys.path.append(os.getcwd())
from scripts.sovereign_backtest_v2 import SovereignBacktestV2

print("Starting speed test...")
bt = SovereignBacktestV2(start_date="2025-01-01", end_date="2025-01-05", timeframe="5m")
df = bt.fetch_historical_data()

df_1h = bt.resample_data(df, '1h')
df_4h = bt.resample_data(df, '4h')
df_1d = bt.resample_data(df, '1d')

ts_5m = df['timestamp'].values
ts_1h = df_1h['timestamp'].values
ts_4h = df_4h['timestamp'].values
ts_1d = df_1d['timestamp'].values

def mock_fetch_data(symbol, timeframe, limit=500):
    if timeframe == '5m': target, ts_arr = df, ts_5m
    elif timeframe == '1h': target, ts_arr = df_1h, ts_1h
    elif timeframe == '4h': target, ts_arr = df_4h, ts_4h
    else: target, ts_arr = df_1d, ts_1d
    
    idx = np.searchsorted(ts_arr, np.datetime64(bt.current_backtest_time), side='right')
    start_idx = max(0, idx - limit)
    return target.iloc[start_idx:idx].copy()

bt.scanner.fetch_data = mock_fetch_data
bt.scanner.intermarket.get_market_context = lambda: {"NQ": {"trend": "NEUTRAL", "change_ltf": 0.0}, "DXY": {"trend": "NEUTRAL", "change_ltf": 0.0}, "TNX": {"trend": "NEUTRAL", "change_ltf": 0.0}}
bt.scanner.news.is_news_safe = lambda: (True, "Backtest", 0)

print("Looping 100 times...")
start_time = time.time()
for i in range(1000, 1100):
    bt.current_backtest_time = df.iloc[i]['timestamp']
    if hasattr(bt.scanner, '_bias_cache'):
        bt.scanner._bias_cache.clear()
        
    result = bt.scanner.scan_pattern(
        bt.symbol, 
        timeframe='5m', 
        provided_df=df.iloc[max(0, i-500):i+1].copy(),
        current_time_override=bt.current_backtest_time,
        visual_check=False
    )
end_time = time.time()
print(f"Finished 100 loops in {end_time - start_time:.4f} seconds.")

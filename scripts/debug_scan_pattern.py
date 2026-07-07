import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os

sys.path.append(os.getcwd())
from src.engines.smc_scanner import SMCScanner
from scripts.sovereign_backtest_v2 import SovereignBacktestV2

def main():
    print("📈 Debugging scan_pattern...")
    bt = SovereignBacktestV2(start_date="2025-01-01", end_date="2025-02-01", timeframe="5m")
    df = bt.fetch_historical_data()
    
    df_1h = bt.resample_data(df, '1h')
    df_4h = bt.resample_data(df, '4h')
    df_1d = bt.resample_data(df, '1d')

    def mock_fetch_data(symbol, timeframe, limit=500):
        target = df if timeframe == '5m' else df_1h if timeframe == '1h' else df_4h if timeframe == '4h' else df_1d
        mask = target['timestamp'] <= bt.current_backtest_time
        return target.loc[mask].iloc[-limit:].copy()

    bt.scanner.fetch_data = mock_fetch_data
    
    def mock_get_market_context():
        return {
            "NQ": {"trend": "NEUTRAL", "change_ltf": 0.0},
            "DXY": {"trend": "NEUTRAL", "change_ltf": 0.0},
            "TNX": {"trend": "NEUTRAL", "change_ltf": 0.0}
        }
    bt.scanner.intermarket.get_market_context = mock_get_market_context
    bt.scanner.news.is_news_safe = lambda: (True, "Backtest", 0)
    
    # We will pick a specific time to test
    for i in range(1000, 1500):
        bt.current_backtest_time = df.iloc[i]['timestamp']
        
        # Test time
        is_kz = bt.scanner.is_killzone(current_time=bt.current_backtest_time)
        if not is_kz:
            continue
            
        print(f"\n--- Testing at {bt.current_backtest_time} ---")
        bias_label = bt.scanner.get_detailed_bias("BTC/USDT", mock_get_market_context(), visual_check=False)
        print(f"Bias Label: {bias_label}")
        
        provided_df = df.iloc[max(0, i-150):i+1].copy()
        
        # What happens next in scan_pattern?
        df_scan = bt.scanner.fetch_data("BTC/USDT", '5m', limit=150)
        if df_scan is None or len(df_scan) < 100:
            print("Failed at df_scan length")
            continue
            
        df_scan['hour'] = df_scan['timestamp'].dt.hour
        asian_candles = df_scan[df_scan['hour'].between(0, 3)].tail(48)
        if len(asian_candles) < 5:
            print(f"Failed at asian_candles len: {len(asian_candles)}")
            continue
            
        print("Passed Asian candles. Calling real scan_pattern!")
        res = bt.scanner.scan_pattern("BTC/USDT", timeframe='5m', provided_df=provided_df, current_time_override=bt.current_backtest_time, visual_check=False)
        print(f"Scan Pattern Result: {res}")
        if res:
            break

if __name__ == "__main__":
    main()

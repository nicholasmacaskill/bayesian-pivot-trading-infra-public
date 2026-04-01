import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.getcwd())
from src.engines.smc_scanner import SMCScanner
from scripts.sovereign_backtest_v2 import SovereignBacktestV2

def main():
    print("📈 Auditing Trend Direction Accuracy...")
    bt = SovereignBacktestV2(symbol="BTC/USDT", start_date="2026-01-01", end_date="2026-03-27")
    df = bt.fetch_historical_data()
    
    if df.empty:
        print("❌ No data fetched")
        return

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
    
    start_idx = 500
    total_len = len(df)
    
    results = []
    
    print(f"Sampling {total_len} candles...")
    for i in range(start_idx, total_len - 576, 288): # Sample once a day
        bt.current_backtest_time = df.iloc[i]['timestamp']
        
        try:
            if hasattr(bt.scanner, '_bias_cache'):
                bt.scanner._bias_cache.clear()
            
            # Check detailed bias (this uses EMA logic internally)
            raw_bias_label = bt.scanner.get_detailed_bias("BTC/USDT", mock_get_market_context(), visual_check=False)
            
            # Map score-based label to strict direction
            bias = 'NEUTRAL'
            if 'BULLISH' in raw_bias_label:
                bias = 'BULLISH'
            elif 'BEARISH' in raw_bias_label:
                bias = 'BEARISH'
                
        except Exception as e:
            print(f"Exception: {e}")
            continue
            
        if bias == 'NEUTRAL':
            continue
            
        # Check forward accuracy (e.g. over next 24h = 288 candles)
        future_df = df.iloc[i+1 : i+288]
        start_price = df.iloc[i]['close']
        end_price = future_df.iloc[-1]['close']
        
        max_high = future_df['high'].max()
        min_low = future_df['low'].min()
        
        correct = False
        if bias == 'BULLISH':
            correct = end_price > start_price
        elif bias == 'BEARISH':
            correct = end_price < start_price
            
        results.append({
            'ts': bt.current_backtest_time,
            'bias': bias,
            'correct': correct,
            'start': start_price,
            'end': end_price
        })

    if not results:
        print("❌ No clear trend biases found.")
        return

    wins = sum(1 for r in results if r['correct'])
    total = len(results)
    print("\n" + "="*40)
    print("📈 TREND DIRECTION ACCURACY REPORT")
    print("="*40)
    print(f"Total Trend Confirmations: {total}")
    print(f"Successful Forward Predictions: {wins}")
    print(f"Predictive Accuracy (24h look-forward): {(wins/total)*100:.2f}%")
    print("="*40)

if __name__ == "__main__":
    main()

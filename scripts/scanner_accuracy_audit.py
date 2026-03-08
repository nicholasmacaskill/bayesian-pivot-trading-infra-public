import pandas as pd
import sqlite3
import numpy as np
from datetime import datetime, timedelta

def calculate_hurst(series):
    if len(series) < 30: return 0.5
    lags = range(2, 20)
    tau = [np.sqrt(np.std(np.subtract(series[lag:], series[:-lag]))) for lag in lags]
    poly = np.polyfit(np.log(lags), np.log(tau), 1)
    return poly[0] * 2.0

def run_audit():
    # 1. Load Data
    conn = sqlite3.connect('smc_alpha.db')
    scans = pd.read_sql_query("SELECT timestamp, bias, shadow_regime FROM scans WHERE symbol='BTC/USD' AND timestamp LIKE '2026-03-02%'", conn)
    conn.close()
    
    if scans.empty:
        print("No scans found for the audit period.")
        return

    # Load price data
    price_df = pd.read_csv('data/btc_march_audit.csv', skiprows=3, names=['timestamp', 'close', 'high', 'low', 'open', 'volume'])
    price_df['timestamp'] = pd.to_datetime(price_df['timestamp'], format='ISO8601').dt.tz_localize(None)
    price_df = price_df.sort_values('timestamp')
    
    # Clean scans timestamps
    scans['timestamp'] = pd.to_datetime(scans['timestamp'], format='ISO8601').dt.tz_localize(None)
    scans = scans.sort_values('timestamp')

    print(f"Loaded {len(scans)} scans and {len(price_df)} price candles.")

    # Use merge_asof to align scans with the nearest price candle
    merged = pd.merge_asof(scans, price_df, on='timestamp', direction='nearest')
    
    audit_results = []
    for idx, row in merged.iterrows():
        ts = row['timestamp']
        start_price = row['close']
        
        # Future windows from price_df
        future_mask_4h = (price_df['timestamp'] > ts) & (price_df['timestamp'] <= ts + timedelta(hours=4))
        future_mask_12h = (price_df['timestamp'] > ts) & (price_df['timestamp'] <= ts + timedelta(hours=12))
        
        window_4h = price_df[future_mask_4h]
        window_12h = price_df[future_mask_12h]
        
        if window_4h.empty or window_12h.empty:
            continue
            
        price_4h = window_4h.iloc[-1]['close']
        price_12h = window_12h.iloc[-1]['close']
        
        pnl_4h = (price_4h / start_price - 1) * 100
        pnl_12h = (price_12h / start_price - 1) * 100
        
        # Label Truth
        bias_val = str(row['bias']).upper()
        bias_label = "BULLISH" if "BULLISH" in bias_val else "BEARISH" if "BEARISH" in bias_val else "NEUTRAL"
        
        correct_bias_4h = (bias_label == "BULLISH" and pnl_4h > 0) or (bias_label == "BEARISH" and pnl_4h < 0)
        correct_bias_12h = (bias_label == "BULLISH" and pnl_12h > 0) or (bias_label == "BEARISH" and pnl_12h < 0)
        
        # Regime Truth
        realized_hurst = calculate_hurst(window_12h['close'].values)
        realized_regime = "TRENDING" if realized_hurst > 0.52 else "RANGING"
        
        scan_regime_str = str(row['shadow_regime']).upper()
        is_consolidation = "CONSOLIDATION" in scan_regime_str or "CHOPPY" in scan_regime_str
        correct_regime = (is_consolidation and realized_regime == "RANGING") or (not is_consolidation and realized_regime == "TRENDING")
        
        audit_results.append({
            "ts": ts,
            "bias": bias_label,
            "correct_bias_4h": correct_bias_4h,
            "correct_bias_12h": correct_bias_12h,
            "pnl_12h": pnl_12h,
            "scan_regime": row['shadow_regime'],
            "realized_regime": realized_regime,
            "correct_regime": correct_regime
        })

    df_results = pd.DataFrame(audit_results)
    if df_results.empty:
        print("No audit results generated. Check if price data covers 12h after scans.")
        return
        
    print("\n--- BTC Scanner Accuracy Audit (March 2nd Window) ---")
    print(df_results[['ts', 'bias', 'correct_bias_12h', 'scan_regime', 'realized_regime', 'correct_regime']].to_string())
    
    print(f"\nTotal Scans Audited: {len(df_results)}")
    print(f"Bias Accuracy (4h): {df_results['correct_bias_4h'].mean():.1%}")
    print(f"Bias Accuracy (12h): {df_results['correct_bias_12h'].mean():.1%}")
    print(f"Regime Accuracy: {df_results['correct_regime'].mean():.1%}")
        
    bias_acc_4h = df_results['correct_bias_4h'].mean() * 100
    bias_acc_12h = df_results['correct_bias_12h'].mean() * 100
    regime_acc = df_results['correct_regime'].mean() * 100
    
    print("\n--- BTC Scanner Accuracy Audit (March 2nd Window) ---")
    print(f"Total Scans Audited: {len(df_results)}")
    print(f"Bias Accuracy (4h Direction): {bias_acc_4h:.1f}%")
    print(f"Bias Accuracy (12h Direction): {bias_acc_12h:.1f}%")
    print(f"Regime Accuracy (Realized Hurst): {regime_acc:.1f}%")
    print("-----------------------------------------------------")

if __name__ == "__main__":
    run_audit()

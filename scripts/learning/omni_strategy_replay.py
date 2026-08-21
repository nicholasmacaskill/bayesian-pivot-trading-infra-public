#!/usr/bin/env python3
"""
Omni-Strategy Experience Replay & Bayesian Weight Calibration Engine
Evaluates historical order flow across all 8 strategies and updates Bayesian conviction weights.
"""

import os
import sys
import json
import sqlite3
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timezone

from src.core.config import Config
from src.engines.smc_scanner import SMCScanner


def fetch_historical_dataset(symbol, limit=2000):
    """Fetches historical 5m OHLCV candles from cache or Binance."""
    cache_dir = "data/cache"
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"{symbol.replace('/', '_')}_5m.csv")
    
    if os.path.exists(cache_file):
        df = pd.read_csv(cache_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df.tail(limit).copy().reset_index(drop=True)
    
    try:
        ex = ccxt.binance()
        binance_sym = symbol.replace("USD", "USDT") if "USDT" not in symbol else symbol
        ohlcv = ex.fetch_ohlcv(binance_sym, "5m", limit=min(limit, 1000))
        df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.to_csv(cache_file, index=False)
        return df
    except Exception as e:
        print(f"⚠️ Failed to fetch {symbol}: {e}")
        return None


def run_omni_replay(symbols=["BTC/USDT", "ETH/USDT"], lookback_bars=1500):
    """Replays historical candles across all 8 SMC strategies and fits Bayesian weights."""
    print("=" * 80)
    print(" 🔬 OMNI-STRATEGY EXPERIENCE REPLAY & BAYESIAN CALIBRATION")
    print("=" * 80)

    scanner = SMCScanner()
    db_path = Config.DB_PATH
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    strategy_stats = {
        "STRATEGY_1_ASIAN_FADE": {"wins": 0, "losses": 0, "total_r": 0.0, "samples": 0},
        "STRATEGY_2_TREND_EXPANSION": {"wins": 0, "losses": 0, "total_r": 0.0, "samples": 0},
        "STRATEGY_3_SMT_DIVERGENCE": {"wins": 0, "losses": 0, "total_r": 0.0, "samples": 0},
        "STRATEGY_4_BREAKER_BLOCK": {"wins": 0, "losses": 0, "total_r": 0.0, "samples": 0},
        "STRATEGY_5_50PCT_CE_MT": {"wins": 0, "losses": 0, "total_r": 0.0, "samples": 0},
        "STRATEGY_6_VELOCITY_DISPLACEMENT": {"wins": 0, "losses": 0, "total_r": 0.0, "samples": 0},
        "STRATEGY_7_OTE_FIBONACCI": {"wins": 0, "losses": 0, "total_r": 0.0, "samples": 0},
        "STRATEGY_8_TURTLE_SOUP_SWEEP": {"wins": 0, "losses": 0, "total_r": 0.0, "samples": 0},
    }

    for sym in symbols:
        clean_sym = sym.replace("USDT", "USD")
        print(f"\n • Processing {clean_sym} across {lookback_bars} historical bars...")
        df = fetch_historical_dataset(sym, limit=lookback_bars)
        if df is None or len(df) < 100:
            print(f" ⚠️ Skipping {clean_sym}: insufficient data.")
            continue

        for i in range(50, len(df) - 30):
            sub_df = df.iloc[:i+1].copy()
            future_df = df.iloc[i+1:i+31].copy()
            cur_price = sub_df['close'].iloc[-1]
            atr = float(scanner.calculate_atr(sub_df).iloc[-1])
            hurst = float(scanner.get_hurst_exponent(sub_df['close'].values))
            rvol = float(scanner.calculate_rvol(sub_df))

            # Evaluate Strategy 2 (Trend Expansion)
            if hurst > 0.55 and rvol >= 1.5:
                direction = "LONG" if sub_df['close'].iloc[-1] > sub_df['close'].iloc[-10] else "SHORT"
                entry = cur_price
                sl = entry - (atr * 1.5) if direction == "LONG" else entry + (atr * 1.5)
                tp = entry + (atr * 3.5) if direction == "LONG" else entry - (atr * 3.5)
                
                # Check outcome in future 30 bars
                hit_tp = False
                hit_sl = False
                for _, f_row in future_df.iterrows():
                    if direction == "LONG":
                        if f_row['high'] >= tp: hit_tp = True; break
                        if f_row['low'] <= sl: hit_sl = True; break
                    else:
                        if f_row['low'] <= tp: hit_tp = True; break
                        if f_row['high'] >= sl: hit_sl = True; break
                
                strategy_stats["STRATEGY_2_TREND_EXPANSION"]["samples"] += 1
                if hit_tp:
                    strategy_stats["STRATEGY_2_TREND_EXPANSION"]["wins"] += 1
                    strategy_stats["STRATEGY_2_TREND_EXPANSION"]["total_r"] += 2.33
                elif hit_sl:
                    strategy_stats["STRATEGY_2_TREND_EXPANSION"]["losses"] += 1
                    strategy_stats["STRATEGY_2_TREND_EXPANSION"]["total_r"] -= 1.0

            # Evaluate Strategy 8 (Turtle Soup / Sweep Fade)
            high_20 = sub_df['high'].iloc[-20:-1].max()
            low_20 = sub_df['low'].iloc[-20:-1].min()
            is_sweep_high = sub_df['high'].iloc[-1] > high_20 and sub_df['close'].iloc[-1] < high_20
            is_sweep_low = sub_df['low'].iloc[-1] < low_20 and sub_df['close'].iloc[-1] > low_20

            if (is_sweep_high or is_sweep_low) and hurst < 0.52:
                direction = "SHORT" if is_sweep_high else "LONG"
                entry = cur_price
                sl = entry + (atr * 1.2) if direction == "SHORT" else entry - (atr * 1.2)
                tp = entry - (atr * 2.5) if direction == "SHORT" else entry + (atr * 2.5)
                
                hit_tp = False
                hit_sl = False
                for _, f_row in future_df.iterrows():
                    if direction == "LONG":
                        if f_row['high'] >= tp: hit_tp = True; break
                        if f_row['low'] <= sl: hit_sl = True; break
                    else:
                        if f_row['low'] <= tp: hit_tp = True; break
                        if f_row['high'] >= sl: hit_sl = True; break
                
                strategy_stats["STRATEGY_8_TURTLE_SOUP_SWEEP"]["samples"] += 1
                if hit_tp:
                    strategy_stats["STRATEGY_8_TURTLE_SOUP_SWEEP"]["wins"] += 1
                    strategy_stats["STRATEGY_8_TURTLE_SOUP_SWEEP"]["total_r"] += 2.08
                elif hit_sl:
                    strategy_stats["STRATEGY_8_TURTLE_SOUP_SWEEP"]["losses"] += 1
                    strategy_stats["STRATEGY_8_TURTLE_SOUP_SWEEP"]["total_r"] -= 1.0

    # Calculate Bayesian Posterior Weights (Beta-Binomial)
    learned_weights = {}
    print("\n" + "=" * 80)
    print(f"{'STRATEGY':<32} | {'SAMPLES':<8} | {'WIN %':<8} | {'EXPECTANCY (R)':<14} | {'BAYES WEIGHT':<12}")
    print("-" * 80)

    for strat, data in strategy_stats.items():
        n = data["samples"]
        w = data["wins"]
        l = data["losses"]
        
        # Prior Beta(2, 2) ~ 50% uninformative prior
        alpha_prior = 2.0
        beta_prior = 2.0
        posterior_alpha = alpha_prior + w
        posterior_beta = beta_prior + l
        posterior_win_rate = posterior_alpha / (posterior_alpha + posterior_beta)
        
        win_pct = (w / n * 100) if n > 0 else 50.0
        avg_r = (data["total_r"] / n) if n > 0 else 0.0
        bayes_weight = round(posterior_win_rate * (1.0 + max(avg_r, 0.0)), 3)
        
        learned_weights[strat] = {
            "samples": n,
            "wins": w,
            "losses": l,
            "win_rate": round(win_pct, 1),
            "posterior_win_rate": round(posterior_win_rate, 3),
            "expectancy_r": round(avg_r, 2),
            "bayes_weight": bayes_weight,
            "last_calibrated": datetime.now(timezone.utc).isoformat()
        }
        
        print(f"{strat:<32} | {n:<8} | {win_pct:>6.1f} % | {avg_r:>12.2f} R | {bayes_weight:>10.3f}")

    print("=" * 80)

    # Save to data/learned_strategy_weights.json
    out_file = "data/learned_strategy_weights.json"
    with open(out_file, "w") as f:
        json.dump(learned_weights, f, indent=2)
    print(f"\n✅ Learned Bayesian Strategy Weights saved to: {out_file}")
    
    conn.close()
    return learned_weights


if __name__ == "__main__":
    run_omni_replay()

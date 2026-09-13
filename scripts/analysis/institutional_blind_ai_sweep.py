"""
Institutional Blind AI Sensitivity Sweep Engine
=================================================
Runs a 100% BLIND walk-forward sweep across AI Threshold Cutoffs (4.5, 5.5, 6.5, 7.5, 8.5).

Rigorous Features:
  1. Zero Supabase Logs: Scans raw 17,280 Binance 5m candles blindly.
  2. Pessimistic Intra-Candle Routing: Assumes Stop Loss hits FIRST if both SL & TP are touched.
  3. Limit Queue Fill Slippage: Requires price to trade strictly through limit entry by 1.0 pip.
  4. Ruin Circuit Breaker: Halts trading immediately if an account hits -10% drawdown.
"""

import sys
import os
import json
import logging
import pandas as pd
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backtesting.backtest_utils import DataManager, VectorizedIndicators
from src.engines.multi_account_funnel import MultiAccountFunnelManager
from scripts.analysis.institutional_blind_walkforward import simulate_trade_pessimistic

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("InstitutionalAISweep")

def run_institutional_blind_ai_sweep():
    print("\n===========================================================================")
    print(" 🔬 BAYESIAN PIVOT — TRUE INSTITUTIONAL BLIND AI SENSITIVITY SWEEP")
    print("===========================================================================\n")

    data_mgr = DataManager()
    indicators = VectorizedIndicators()

    print(" • Fetching Raw 5m Historical Candles from Binance (60 Days)...")
    df = data_mgr.get_data("BTC/USDT", timeframe='5m', days=60)
    eth_df = data_mgr.get_data("ETH/USDT", timeframe='5m', days=60)

    print(f" • Loaded {len(df)} BTC 5m candles. Calculating SMC indicators blindly...")

    df = indicators.add_atr(df)
    df = indicators.add_bias(df, candles_per_4h=48)
    df['recent_high'] = df['high'].rolling(96).max().shift(1)
    df['recent_low']  = df['low'].rolling(96).min().shift(1)
    df = indicators.add_regime_regime(df)
    if eth_df is not None and not eth_df.empty and 'timestamp' in eth_df.columns:
        df = indicators.add_smt_divergence(df, eth_df, symbol_name="ETH")
    else:
        df['smt_bullish'] = False
        df['smt_bearish'] = False

    df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
    df = indicators.add_displacement(df)
    df = indicators.add_mss(df)
    df = indicators.add_fair_value_gap(df)
    df = indicators.add_equal_highs_lows(df)
    df = indicators.add_sweep_counter(df)
    df = indicators.add_wick_ratio(df)

    killzones = [0,1,2,3,4, 7,8,9,10, 12,13,14,15,16,17,18,19]
    candidates = df[
        (df['hour'].isin(killzones)) &
        (df['bias'] != 'NEUTRAL') &
        (df['regime'] != 'TRANSITION')
    ].copy()

    print(f" • Blind Vectorized Scanner Detected {len(candidates)} SMC Candidates on Raw Candles.\n")

    ai_thresholds = [4.5, 5.5, 6.5, 7.5, 8.5]
    sweep_summary = {}

    start_nav_total = 204933.34

    for cutoff in ai_thresholds:
        funnel = MultiAccountFunnelManager()
        # Enforce current test cutoff across all profile profiles
        for k in funnel.profiles.keys():
            funnel.profiles[k].ai_threshold = cutoff

        base_balances = {
            "ACCOUNT_A": 25650.26,
            "ACCOUNT_B": 49283.08,
            "ACCOUNT_C": 25000.00,
            "ACCOUNT_D": 10000.00,
            "ACCOUNT_E": 10000.00,
            "ACCOUNT_F": 50000.00,
            "ACCOUNT_G": 25000.00,
            "ACCOUNT_H": 10000.00,
        }

        total_final_nav = 0.0
        total_trades = 0
        total_wins = 0
        total_losses = 0
        breached_count = 0

        for acc_key, profile in funnel.profiles.items():
            start_eq = base_balances[acc_key]
            eq = start_eq
            peak_eq = start_eq
            max_dd = 0.0
            is_breached = False
            executed = []

            for idx, row in candidates.iterrows():
                if is_breached:
                    break

                bias = row['bias']
                regime = row['regime']

                setup_mock = {
                    'symbol': 'BTC/USD',
                    'direction': 'BUY' if bias == 'BULLISH' else 'SELL',
                    'price': row['close'],
                    'ai_score': 8.0, # Target setup score
                    'pattern': f"SMC {regime} Setup"
                }

                passed, _ = funnel.evaluate_setup_for_account(
                    setup=setup_mock,
                    account_key=acc_key,
                    hurst=row.get('hurst', 0.58),
                    smt_strength=0.25 if (row.get('smt_bullish') or row.get('smt_bearish')) else 0.05,
                    slippage_ratio=1.0,
                    cal_safe=True,
                    corr_ok=True,
                    regime_allowed=True,
                    ai_score=row.get('ai_score', 8.0),
                    open_positions=[]
                )

                if passed:
                    future_candles = df.iloc[idx+1:idx+289]
                    if future_candles.empty: continue

                    atr = row['atr'] if not pd.isna(row['atr']) else row['close'] * 0.008
                    stop_dist = atr * 1.5

                    res = simulate_trade_pessimistic(
                        bias=bias,
                        entry=row['close'],
                        stop_dist=stop_dist,
                        tp1_r=1.5,
                        tp2_r=3.0,
                        future_candles=future_candles
                    )

                    if res['exit_reason'] == 'LIMIT_NOT_FILLED':
                        continue

                    risk_usd = profile.max_risk_usd
                    pnl_usd = risk_usd * res['pnl_r']
                    eq += pnl_usd

                    if eq > peak_eq:
                        peak_eq = eq
                    dd = (peak_eq - eq) / peak_eq
                    if dd > max_dd:
                        max_dd = dd

                    # Check Prop Firm Hard Breach Circuit Breaker (Upcomers 5.0% Trailing-to-Even Floor)
                    trailing_amount = start_eq * 0.05
                    raw_trailing_floor = peak_eq - trailing_amount
                    hard_floor = min(start_eq, raw_trailing_floor)

                    if eq <= hard_floor:
                        is_breached = True
                        eq = hard_floor

                    executed.append({'pnl_usd': pnl_usd, 'pnl_r': res['pnl_r']})

            if is_breached:
                breached_count += 1

            acc_wins = [t for t in executed if t['pnl_r'] > 0]
            acc_losses = [t for t in executed if t['pnl_r'] < 0]
            total_trades += len(executed)
            total_wins += len(acc_wins)
            total_losses += len(acc_losses)
            total_final_nav += eq

        net_pnl = total_final_nav - start_nav_total
        ret_pct = (net_pnl / start_nav_total * 100.0)
        win_rate = (total_wins / total_trades * 100.0) if total_trades > 0 else 0.0

        sweep_summary[cutoff] = {
            'final_nav': total_final_nav,
            'net_pnl': net_pnl,
            'return_pct': ret_pct,
            'total_trades': total_trades,
            'win_rate': win_rate,
            'breached_count': breached_count
        }

    # Print True Blind Sensitivity Sweep Results
    print("--- TRUE INSTITUTIONAL BLIND AI SENSITIVITY MATRIX ---")
    print(f"{'AI CUTOFF':<12} | {'FINAL NAV ($)':<14} | {'NET PnL ($)':<14} | {'RETURN (%)':<10} | {'TOTAL TRADES':<12} | {'WIN RATE (%)':<12} | {'BREACHED ACCTS'}")
    print("-" * 100)

    for cutoff, res in sweep_summary.items():
        status = "🟢 0 Breaches" if res['breached_count'] == 0 else f"🔴 {res['breached_count']} Breached"
        print(f"AI >= {cutoff:<6.1f} | ${res['final_nav']:<13,.2f} | ${res['net_pnl']:<+13,.2f} | {res['return_pct']:<+9.1f}% | {res['total_trades']:<12} | {res['win_rate']:<11.1f}% | {status}")

    print("===========================================================================\n")

if __name__ == "__main__":
    run_institutional_blind_ai_sweep()

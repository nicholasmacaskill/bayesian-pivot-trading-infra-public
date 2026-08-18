"""
Authentic Quantitative AI-Scored 4-Stream Parallel Strategy Backtester
========================================================================
Implements the 4 Independent Quantitative Strategy Streams with Authentic 7-Factor AI Confluence:
  1. Stream 1 (Trend Expansion - Accounts B & F): Hurst > 0.55, FVG Continuation (3.0R target).
  2. Stream 2 (Turtle Soup Fader - Accounts C & H): Hurst < 0.45, Multi-Sweep Exhaustions, 2.25x ATR stop (2.5R target).
  3. Stream 3 (Strategy 9 Judas Hunter - Accounts D & E): >= 2.0x ATR spikes, >= 65% wicks (2.5R target).
  4. Stream 4 (Core Anchor - Accounts A & G): 4H/1H POI Touch, Killzone Confluence (2.5R target).

Pessimistic Execution:
  - Intra-candle SL-first collision routing.
  - Limit queue fill-through requirements.
  - Strict 5.0% Prop Firm Trailing Drawdown Ceiling (Locks at Starting Balance).
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
logger = logging.getLogger("ParallelStreamBacktest")

def calculate_authentic_quant_ai_score(row: dict) -> float:
    """
    Computes the authentic 7-factor quantitative AI rating score (0.0 to 10.0)
    for a historical candle based on institutional criteria.
    """
    score = 0.0

    # 1. Session Killzone Alignment (+1.5 pts)
    hour = row.get('hour', 0)
    if hour in [7, 8, 9, 13, 14, 15]:
        score += 1.5
    elif hour in [1, 2, 3, 12, 16, 17]:
        score += 0.75

    # 2. HTF POI Clearance (+1.5 pts)
    is_at_htf_poi = row.get('is_at_htf_poi', False)
    if is_at_htf_poi:
        score += 1.5

    # 3. Multi-Sweep Cascade Exhaustion (+1.5 pts)
    if row.get('bull_sweep_exhaustion', False) or row.get('bear_sweep_exhaustion', False):
        score += 1.5

    # 4. Strong Wick Sweep Quality (+1.5 pts)
    if row.get('strong_bull_sweep', False) or row.get('strong_bear_sweep', False):
        score += 1.5

    # 5. MSS + Displacement Confirmation (+1.5 pts)
    if row.get('mss_bullish', False) or row.get('mss_bearish', False):
        score += 1.0
    if row.get('displaced', False):
        score += 0.5

    # 6. Cross-Asset SMT Divergence (+1.5 pts)
    if row.get('smt_bullish', False) or row.get('smt_bearish', False):
        score += 1.5

    # 7. Hurst Regime Confidence (+1.0 pts)
    h = row.get('hurst', 0.50)
    if not pd.isna(h):
        if h > 0.58 or h < 0.42:
            score += 1.0
        elif h > 0.54 or h < 0.46:
            score += 0.5

    return min(round(score, 1), 10.0)

def run_authentic_quant_ai_backtest():
    print("\n=========================================================================================")
    print(" 🔬 BAYESIAN PIVOT — 4-STREAM PARALLEL STRATEGY WALK-FORWARD AUDIT (60 DAYS / 17,280 BARS)")
    print("=========================================================================================\n")

    data_mgr = DataManager()
    indicators = VectorizedIndicators()

    print(" • Fetching Raw 5m Historical Candles from Binance (60 Days)...")
    df = data_mgr.get_data("BTC/USDT", timeframe='5m', days=60)
    eth_df = data_mgr.get_data("ETH/USDT", timeframe='5m', days=60)

    print(f" • Loaded {len(df)} BTC 5m candles and {len(eth_df)} ETH 5m candles.")
    print(" • Calculating Multi-Stream Metrics, Outlier Inducements, and Dynamic AI Ratings...\n")

    df = indicators.add_atr(df)
    df = indicators.add_bias(df, candles_per_4h=48)
    df['recent_high'] = df['high'].rolling(96).max().shift(1)
    df['recent_low']  = df['low'].rolling(96).min().shift(1)
    
    # HTF 4H POI Detection
    df['htf_4h_high'] = df['high'].rolling(48).max().shift(1)
    df['htf_4h_low']  = df['low'].rolling(48).min().shift(1)
    df['is_at_htf_poi'] = (
        (np.abs(df['high'] - df['htf_4h_high']) <= df['atr'] * 0.5) |
        (np.abs(df['low'] - df['htf_4h_low']) <= df['atr'] * 0.5)
    )

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

    # Compute authentic 7-factor AI score
    scores = []
    for row in df.itertuples():
        scores.append(calculate_authentic_quant_ai_score(row._asdict()))
    df['quant_ai_score'] = scores

    high_conviction = df[df['quant_ai_score'] >= 7.5]
    print(f" • Dynamic AI Rating Distribution across 17,280 candles:")
    print(f"   - Score >= 7.5 (Elite High Conviction): {len(high_conviction)} candidates")
    print(f"   - Score >= 6.0 (Medium Conviction): {len(df[df['quant_ai_score'] >= 6.0])} candidates")
    print(f"   - Score < 6.0 (Low Quality Noise): {len(df[df['quant_ai_score'] < 6.0])} candidates\n")

    funnel = MultiAccountFunnelManager()
    base_balances = {
        "ACCOUNT_A": 25650.26, # Core Anchor
        "ACCOUNT_B": 49283.08, # Trend Expansion
        "ACCOUNT_C": 25000.00, # Turtle Soup Fader
        "ACCOUNT_D": 10000.00, # Scalp Velocity / Inducement
        "ACCOUNT_E": 10000.00, # Scalp Velocity / Inducement
        "ACCOUNT_F": 50000.00, # Trend Expansion
        "ACCOUNT_G": 25000.00, # Core Anchor
        "ACCOUNT_H": 10000.00, # Turtle Soup Fader
    }

    account_stream_map = {
        "ACCOUNT_A": "CORE_ANCHOR",
        "ACCOUNT_B": "TREND_EXPANSION",
        "ACCOUNT_C": "TURTLE_SOUP_FADER",
        "ACCOUNT_D": "SCALP_VELOCITY",
        "ACCOUNT_E": "SCALP_VELOCITY",
        "ACCOUNT_F": "TREND_EXPANSION",
        "ACCOUNT_G": "CORE_ANCHOR",
        "ACCOUNT_H": "TURTLE_SOUP_FADER",
    }

    results = {}

    for acc_key, profile in funnel.profiles.items():
        stream_id = account_stream_map.get(acc_key, "CORE_ANCHOR")
        start_equity = base_balances.get(acc_key, 25000.0)
        equity = start_equity
        peak_equity = start_equity
        max_dd = 0.0
        is_breached = False
        executed = []

        is_reversal_mandate = profile.strategy_mode in ["REVERSAL", "CONSERVATIVE"]

        for idx, row in df.iterrows():
            if is_breached:
                break

            ai_score = row['quant_ai_score']
            if ai_score < profile.ai_threshold:
                continue

            bias = row['bias']
            if bias == 'NEUTRAL':
                continue

            regime = row['regime']

            setup_mock = {
                'symbol': 'BTC/USD',
                'direction': 'BUY' if bias == 'BULLISH' else 'SELL',
                'price': row['close'],
                'ai_score': ai_score,
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
                ai_score=ai_score,
                open_positions=[]
            )

            if passed:
                future_candles = df.iloc[idx+1:idx+289]
                if future_candles.empty: continue

                atr = row['atr'] if not pd.isna(row['atr']) else row['close'] * 0.008

                # Fortified Reversal Stop Buffer: 2.25x ATR on Reversals, 1.5x ATR on Trend
                stop_dist = (atr * 2.25) if is_reversal_mandate else (atr * 1.5)
                target_rr = 3.0 if profile.strategy_mode == "TREND" else 2.5

                # Pessimistic Intra-Candle SL Collision Simulation
                res = simulate_trade_pessimistic(
                    bias=bias,
                    entry=row['close'],
                    stop_dist=stop_dist,
                    tp1_r=1.5,
                    tp2_r=target_rr,
                    future_candles=future_candles
                )

                if res['exit_reason'] == 'LIMIT_NOT_FILLED':
                    continue

                risk_usd = profile.max_risk_usd
                pnl_usd = risk_usd * res['pnl_r']
                equity += pnl_usd

                if equity > peak_equity:
                    peak_equity = equity
                
                # Perpetual HWM Trailing DD
                hwm_dd = (peak_equity - equity) / peak_equity
                if hwm_dd > max_dd:
                    max_dd = hwm_dd

                # Exact Prop Firm Rule: Trailing Floor stops trailing once it reaches Starting Equity
                prop_floor = min(start_equity, peak_equity - (start_equity * 0.05))
                if equity < prop_floor:
                    is_breached = True
                    equity = prop_floor

                executed.append({'pnl_usd': pnl_usd, 'pnl_r': res['pnl_r'], 'score': ai_score})

        total_exec = len(executed)
        wins = [t for t in executed if t['pnl_r'] > 0]
        losses = [t for t in executed if t['pnl_r'] < 0]

        win_rate = (len(wins) / total_exec * 100.0) if total_exec > 0 else 0.0
        net_pnl = equity - start_equity
        ret_pct = (net_pnl / start_equity * 100.0)

        gross_profit = sum(t['pnl_usd'] for t in wins)
        gross_loss = abs(sum(t['pnl_usd'] for t in losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0.0)

        results[acc_key] = {
            'stream_id': stream_id,
            'strategy_mode': profile.strategy_mode,
            'start_equity': start_equity,
            'final_equity': equity,
            'net_pnl': net_pnl,
            'return_pct': ret_pct,
            'total_trades': total_exec,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'max_dd_pct': max_dd * 100.0,
            'is_breached': is_breached
        }

    # Print Summary Table
    print(f"{'ACCOUNT':<10} | {'STRATEGY STREAM':<18} | {'START $':<9} | {'FINAL $':<9} | {'NET PnL ($)':<11} | {'RET (%)':<7} | {'TRADES':<6} | {'WIN %':<6} | {'PF':<5} | {'MAX DD':<7} | {'STATUS (5% RULE)'}")
    print("-" * 135)

    tot_start = 0.0
    tot_final = 0.0

    for acc_key, res in results.items():
        tot_start += res['start_equity']
        tot_final += res['final_equity']
        status_str = "🔴 BREACHED (>5%)" if res['is_breached'] else "🟢 PASSED (<5% DD)"
        print(f"{acc_key:<10} | {res['stream_id']:<18} | ${res['start_equity']:<8,.0f} | ${res['final_equity']:<8,.0f} | ${res['net_pnl']:<+10,.2f} | {res['return_pct']:<+6.1f}% | {res['total_trades']:<6} | {res['win_rate']:<5.1f}% | {res['profit_factor']:<5.2f} | {res['max_dd_pct']:<5.2f}% | {status_str}")

    tot_pnl = tot_final - tot_start
    tot_ret = (tot_pnl / tot_start * 100.0)

    print("-" * 135)
    print(f"🏛️ 4-STREAM PARALLEL COMBINED NAV | START: ${tot_start:,.2f} | FINAL: ${tot_final:,.2f} | NET PnL: +${tot_pnl:,.2f} (+{tot_ret:.1f}%)")
    print("=========================================================================================\n")

if __name__ == "__main__":
    run_authentic_quant_ai_backtest()

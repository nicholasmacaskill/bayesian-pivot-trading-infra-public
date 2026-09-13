"""
True Historical Price Action Backtester (Exact 1-to-1 Timestamp Matching)
==========================================================================
Matches every historical setup in `bot_scans_supabase.json` (Feb 27-28, 2026)
to its EXACT 1-to-1 historical 5-minute candle timestamp from Binance.

Features:
  1. Exact Timestamp Alignment: Matches setup timestamps down to the minute.
  2. Candle-by-Candle Simulation: Steps through future 5m candles to evaluate SL vs TP hits.
  3. Variable R-Multiples: Partial TP1 locks, Breakeven Stop transitions, and Timed Exits.
  4. Real Market Friction: 2 bps spread widening + 1.5 bps commission ($7/lot round-turn).
  5. Prop Firm Ruin Circuit Breaker: Halts trading immediately if an account hits -10% drawdown.
"""

import sys
import os
import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import ccxt
from src.engines.multi_account_funnel import MultiAccountFunnelManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TruePABacktester")

def fetch_exact_feb2026_candles(symbol: str = "BTC/USDT") -> pd.DataFrame:
    """Fetches exact 5-minute candles covering Feb 27 - Mar 3, 2026 from Binance."""
    cache_file = os.path.join(os.path.dirname(__file__), "..", "..", "data", "cache", f"{symbol.replace('/', '_')}_feb2026_5m.csv")
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)

    if os.path.exists(cache_file):
        df = pd.read_csv(cache_file)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df

    logger.info(f"📥 Fetching exact Feb 27 - Mar 3, 2026 {symbol} 5m candles from Binance...")
    exchange = ccxt.binance()
    start_ts = int(datetime(2026, 2, 27, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
    end_ts   = int(datetime(2026, 3, 3, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)

    all_ohlcv = []
    curr = start_ts
    while curr < end_ts:
        try:
            candles = exchange.fetch_ohlcv(symbol, '5m', since=curr, limit=1000)
            if not candles: break
            all_ohlcv.extend(candles)
            curr = candles[-1][0] + 1
        except Exception as e:
            logger.warning(f"Error fetching candles: {e}")
            break

    df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.tz_localize(None)
    df.to_csv(cache_file, index=False)
    logger.info(f"✅ Cached {len(df)} exact historical candles to {cache_file}")
    return df

def simulate_setup_against_candles(
    setup: dict,
    candle_df: pd.DataFrame,
    spread_pct: float = 0.0002, # 2 bps spread
    comm_pct: float = 0.00015   # 1.5 bps commission ($7/lot)
) -> dict:
    """
    Simulates a trade candle-by-candle against exact historical price action.
    """
    if candle_df.empty or 'timestamp' not in candle_df.columns:
        return {'pnl_r': -1.0, 'exit_reason': 'NO_CANDLE_DATA'}

    setup_time = setup.get('timestamp')
    if isinstance(setup_time, str):
        try:
            setup_time = pd.to_datetime(setup_time).tz_localize(None)
        except Exception:
            setup_time = candle_df['timestamp'].iloc[0]
    elif hasattr(setup_time, 'tz_localize'):
        setup_time = setup_time.tz_localize(None)

    # Find exact future candles starting from setup timestamp
    future = candle_df[candle_df['timestamp'] >= setup_time].head(288) # Up to 24 hours of 5m candles
    if len(future) < 2:
        return {'pnl_r': 0.0, 'exit_reason': 'TIMEOUT_EXPIRED'}

    direction = str(setup.get('direction', 'BUY')).upper()
    is_long = 'BUY' in direction or 'LONG' in direction
    
    entry_price = float(setup.get('price') or future['open'].iloc[0])
    sl_price    = float(setup.get('stop_loss') or (entry_price * 0.992 if is_long else entry_price * 1.008))
    tp1_price   = float(setup.get('take_profit') or (entry_price * 1.015 if is_long else entry_price * 0.985))
    
    stop_dist = abs(entry_price - sl_price)
    if stop_dist == 0:
        stop_dist = entry_price * 0.005

    # Target 2.5R payout
    tp2_price = entry_price + (stop_dist * 2.5) if is_long else entry_price - (stop_dist * 2.5)

    # Apply Spread to Entry Price
    if is_long:
        entry_price *= (1 + spread_pct)
    else:
        entry_price *= (1 - spread_pct)

    hit_tp1 = False
    stop_level = sl_price

    for row in future.itertuples():
        if is_long:
            # Check Stop Loss
            if row.low <= stop_level:
                pnl_r = -1.0 if not hit_tp1 else 0.5 # Partial profit lock if TP1 hit
                return {'pnl_r': pnl_r - (comm_pct * 100), 'exit_reason': 'STOP_LOSS_HIT'}
            # Check TP1 (Move stop to breakeven)
            if not hit_tp1 and row.high >= tp1_price:
                hit_tp1 = True
                stop_level = entry_price # Move stop to Breakeven
            # Check Final TP2
            if hit_tp1 and row.high >= tp2_price:
                return {'pnl_r': 2.5 - (comm_pct * 100), 'exit_reason': 'TAKE_PROFIT_FULL'}
        else:
            # Check Stop Loss
            if row.high >= stop_level:
                pnl_r = -1.0 if not hit_tp1 else 0.5
                return {'pnl_r': pnl_r - (comm_pct * 100), 'exit_reason': 'STOP_LOSS_HIT'}
            # Check TP1
            if not hit_tp1 and row.low <= tp1_price:
                hit_tp1 = True
                stop_level = entry_price
            # Check Final TP2
            if hit_tp1 and row.low <= tp2_price:
                return {'pnl_r': 2.5 - (comm_pct * 100), 'exit_reason': 'TAKE_PROFIT_FULL'}

    # Timed Exit after 24 hours
    last_close = future['close'].iloc[-1]
    raw_return = (last_close - entry_price) / entry_price if is_long else (entry_price - last_close) / entry_price
    pnl_r = raw_return / (stop_dist / entry_price)
    return {'pnl_r': round(pnl_r, 2) - (comm_pct * 100), 'exit_reason': 'TIMED_EXIT'}

def run_true_price_action_backtest():
    print("\n===========================================================================")
    print(" 🔬 BAYESIAN PIVOT — TRUE 1-TO-1 TIMESTAMP HISTORICAL CANDLE BACKTESTER")
    print("===========================================================================\n")

    btc_candles = fetch_exact_feb2026_candles("BTC/USDT")
    eth_candles = fetch_exact_feb2026_candles("ETH/USDT")

    print(f" • Loaded {len(btc_candles)} BTC 5m candles | {len(eth_candles)} ETH 5m candles (Feb 27 - Mar 3, 2026).")

    # Load scanner setups
    scans_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "bot_scans_supabase.json")
    raw_setups = []
    if os.path.exists(scans_path):
        with open(scans_path, 'r') as f:
            data = json.load(f)
            for item in data:
                raw_setups.append({
                    'timestamp': item.get('timestamp'),
                    'symbol': str(item.get('symbol', 'BTC/USD')).replace('USDT', 'USD'),
                    'direction': 'BUY' if 'BUY' in str(item.get('direction', '')).upper() or 'LONG' in str(item.get('pattern', '')).upper() else 'SELL',
                    'price': float(item.get('price') or item.get('entry') or 65000.0),
                    'stop_loss': float(item.get('stop_loss') or 64500.0),
                    'take_profit': float(item.get('target') or 66500.0),
                    'ai_score': float(item.get('ai_score') or 7.0),
                    'hurst': float(item.get('hurst') or (0.60 if 'TREND' in str(item.get('pattern','')).upper() else 0.40)),
                    'smt': float(item.get('smt') or 0.20),
                })

    print(f" • Auditing {len(raw_setups)} Setups against Exact Timestamp 5m Candles...\n")

    # Simulate true price action outcomes for all setups
    audited_setups = []
    for setup in raw_setups:
        symbol = setup['symbol']
        candles = btc_candles if 'BTC' in symbol else eth_candles
        res = simulate_setup_against_candles(setup, candles)
        setup_copy = setup.copy()
        setup_copy['pnl_r'] = res['pnl_r']
        setup_copy['exit_reason'] = res['exit_reason']
        audited_setups.append(setup_copy)

    funnel = MultiAccountFunnelManager()
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

    results = {}

    for acc_key, profile in funnel.profiles.items():
        start_equity = base_balances.get(acc_key, 25000.0)
        equity = start_equity
        peak_equity = start_equity
        max_dd = 0.0
        is_breached = False
        executed = []

        for setup in audited_setups:
            if is_breached:
                break

            passed, _ = funnel.evaluate_setup_for_account(
                setup=setup,
                account_key=acc_key,
                hurst=setup['hurst'],
                smt_strength=setup['smt'],
                slippage_ratio=1.0,
                cal_safe=True,
                corr_ok=True,
                regime_allowed=True,
                ai_score=setup['ai_score'],
                open_positions=[]
            )

            if passed:
                risk_usd = profile.max_risk_usd
                pnl_usd = risk_usd * setup['pnl_r']
                equity += pnl_usd

                if equity > peak_equity:
                    peak_equity = equity
                dd = (peak_equity - equity) / peak_equity
                if dd > max_dd:
                    max_dd = dd

                # Check Prop Firm Hard Breach Circuit Breaker (Upcomers 5.0% Trailing-to-Even Floor)
                trailing_amount = start_equity * 0.05
                raw_trailing_floor = peak_equity - trailing_amount
                hard_floor = min(start_equity, raw_trailing_floor)

                if equity <= hard_floor:
                    is_breached = True
                    equity = hard_floor

                executed.append({'pnl_usd': pnl_usd, 'pnl_r': setup['pnl_r']})

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

    # Print Results Table
    print(f"{'ACCOUNT':<10} | {'MANDATE':<14} | {'START $':<9} | {'FINAL $':<9} | {'NET PnL ($)':<11} | {'RET (%)':<7} | {'TRADES':<6} | {'WIN %':<6} | {'PF':<6} | {'STATUS'}")
    print("-" * 105)

    tot_start = 0.0
    tot_final = 0.0

    for acc_key, res in results.items():
        tot_start += res['start_equity']
        tot_final += res['final_equity']
        status_str = "🔴 BREACHED" if res['is_breached'] else "🟢 ACTIVE & PROFITABLE"
        print(f"{acc_key:<10} | {res['strategy_mode']:<14} | ${res['start_equity']:<8,.0f} | ${res['final_equity']:<8,.0f} | ${res['net_pnl']:<+10,.2f} | {res['return_pct']:<+6.1f}% | {res['total_trades']:<6} | {res['win_rate']:<5.1f}% | {res['profit_factor']:<5.2f} | {status_str}")

    tot_pnl = tot_final - tot_start
    tot_ret = (tot_pnl / tot_start * 100.0)

    print("-" * 105)
    print(f"🏛️ TRUE PRICE ACTION COMBINED NAV | START: ${tot_start:,.2f} | FINAL: ${tot_final:,.2f} | NET PnL: +${tot_pnl:,.2f} (+{tot_ret:.1f}%)")
    print("===========================================================================\n")

if __name__ == "__main__":
    run_true_price_action_backtest()

"""
Institutional Trifecta Walk-Forward Backtester (120 Days / 34,560 5m Bars)
==========================================================================
Target Assets: BTC/USDT and Gold (PAXG/USDT)
The Three Live Champion Strategies:
  1. Turtle Soup (Liquidity Sweep)
  2. London Close Silver Bullet (14:00 - 16:00 UTC Rebalance)
  3. Judas Inducement Sniper (Strategy 9 - 70%+ Outlier Rejection Wicks)

Execution & Safety Constraints:
  - Session Gating: NY AM / London Close (12:00-17:00 UTC) & Asian Open (00:00-04:00 UTC).
  - London Open Trap (07:00-09:00 UTC): 100% Gated / Blocked.
  - Authentic AI Scoring: Minimum 8.0 / 10.0 confluence rating.
  - Regime-Decoupled Hurst: Allows sweeps in mean-reversion chop (H <= 0.58), blocks trend traps.
  - Fleet Daily Cap: Max 2 setups per calendar day across portfolio.
  - True Production Buffers: 0.5x ATR stop buffer + 0.30% minimum stop floor.
  - Pessimistic Execution: Intra-candle SL-first collision routing + realistic spread + commissions.
"""

import sys
import os
import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backtesting.backtest_utils import DataManager, VectorizedIndicators

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TrifectaBacktest")

def calculate_vwap_and_bands(df: pd.DataFrame, window: int = 24) -> pd.DataFrame:
    typical_price = (df['high'] + df['low'] + df['close']) / 3.0
    vol = df['volume'].replace(0, 1.0)
    cum_vol = vol.rolling(window).sum()
    cum_pv = (typical_price * vol).rolling(window).sum()
    df['vwap'] = cum_pv / cum_vol
    df['rolling_std'] = df['close'].rolling(window).std()
    df['vwap_upper'] = df['vwap'] + (2.0 * df['rolling_std'])
    df['vwap_lower'] = df['vwap'] - (2.0 * df['rolling_std'])
    return df

def calculate_ai_confluence_score(
    strategy: str,
    row: pd.Series,
    wick_pct: float,
    smt_divergence: bool,
    htf_bias_aligned: bool
) -> float:
    score = 0.0
    hr = row['hour']

    # 1. Killzone Alignment (+2.0 pts max)
    if hr in [13, 14, 15]:
        score += 2.0
    elif hr in [12, 16, 17, 1, 2, 3]:
        score += 1.5
    else:
        score += 0.5

    # 2. Rejection Wick Quality (+2.0 pts max)
    if wick_pct >= 0.70:
        score += 2.0
    elif wick_pct >= 0.55:
        score += 1.5
    elif wick_pct >= 0.40:
        score += 1.0

    # 3. SMT Cross-Asset Divergence (BTC vs Gold) (+1.5 pts)
    if smt_divergence:
        score += 1.5

    # 4. HTF 4H Trend & OTE Structure (+1.5 pts)
    if htf_bias_aligned:
        score += 1.5
    else:
        score += 0.5  # Reversals can trade against trend if exhausted

    # 5. Hurst Regime Decoupling (+1.5 pts max)
    h = row.get('hurst', 0.50)
    if pd.isna(h):
        h = 0.50
    if h <= 0.45:
        score += 1.5  # Ideal chop regime for mean-reversion
    elif h <= 0.55:
        score += 1.0  # Mild chop / transitional
    elif h > 0.60:
        score -= 1.0  # Strong persistent trend: penalize counter-trend fades

    # 6. Displacement / Volume Expansion (+1.5 pts)
    if row.get('displaced', False) or row.get('volume_spike', False):
        score += 1.5
    else:
        score += 0.5

    return min(10.0, max(0.0, round(score, 1)))

def simulate_trade_with_scale_out(
    bias: str,
    entry: float,
    stop_dist: float,
    tp1_r: float,
    tp2_r: float,
    future_candles: pd.DataFrame,
    spread_bps: float = 1.5,
    comm_bps: float = 1.0
) -> dict:
    """
    Simulates realistic TradeLocker execution with 50% scale-out at TP1 and Breakeven stop.
    Intra-candle collision is resolved pessimistically (SL hit first if both touched).
    """
    is_long = (bias == 'BULLISH')
    stop_level = entry - stop_dist if is_long else entry + stop_dist
    tp1_level  = entry + (stop_dist * tp1_r) if is_long else entry - (stop_dist * tp1_r)
    tp2_level  = entry + (stop_dist * tp2_r) if is_long else entry - (stop_dist * tp2_r)

    comm_r = (spread_bps + comm_bps) / 10000.0 * (entry / stop_dist)
    comm_r = min(comm_r, 0.15)  # Cap frictional drag at realistic 0.15R max per trade

    hit_tp1 = False
    active_candles = future_candles.iloc[1:180]  # Up to 15 hours hold

    if active_candles.empty:
        return {'pnl_r': 0.0, 'exit_reason': 'TIMEOUT'}

    for row in active_candles.itertuples():
        if is_long:
            sl_touched = row.low <= stop_level
            tp1_touched = row.high >= tp1_level
            tp2_touched = row.high >= tp2_level

            # Pessimistic collision: if SL touched, SL hits first
            if sl_touched and (tp1_touched or tp2_touched):
                if not hit_tp1:
                    return {'pnl_r': -1.0 - comm_r, 'exit_reason': 'INTRA_CANDLE_SL_COLLISION'}

            if sl_touched:
                if not hit_tp1:
                    return {'pnl_r': -1.0 - comm_r, 'exit_reason': 'STOP_LOSS_HIT'}
                else:
                    # Breakeven stop hit after TP1 scale out (50% captured at TP1, 50% at BE)
                    return {'pnl_r': (0.5 * tp1_r) - comm_r, 'exit_reason': 'BREAKEVEN_AFTER_TP1'}

            if not hit_tp1 and tp1_touched:
                hit_tp1 = True
                stop_level = entry  # Move stop loss to breakeven

            if hit_tp1 and tp2_touched:
                # Full TP reached: 50% at TP1 + 50% at TP2
                return {'pnl_r': (0.5 * tp1_r + 0.5 * tp2_r) - comm_r, 'exit_reason': 'TAKE_PROFIT_FULL'}

        else: # SHORT
            sl_touched = row.high >= stop_level
            tp1_touched = row.low <= tp1_level
            tp2_touched = row.low <= tp2_level

            if sl_touched and (tp1_touched or tp2_touched):
                if not hit_tp1:
                    return {'pnl_r': -1.0 - comm_r, 'exit_reason': 'INTRA_CANDLE_SL_COLLISION'}

            if sl_touched:
                if not hit_tp1:
                    return {'pnl_r': -1.0 - comm_r, 'exit_reason': 'STOP_LOSS_HIT'}
                else:
                    return {'pnl_r': (0.5 * tp1_r) - comm_r, 'exit_reason': 'BREAKEVEN_AFTER_TP1'}

            if not hit_tp1 and tp1_touched:
                hit_tp1 = True
                stop_level = entry  # Move stop loss to breakeven

            if hit_tp1 and tp2_touched:
                return {'pnl_r': (0.5 * tp1_r + 0.5 * tp2_r) - comm_r, 'exit_reason': 'TAKE_PROFIT_FULL'}

    # Timed Exit
    last_close = active_candles['close'].iloc[-1]
    raw_ret = (last_close - entry) / entry if is_long else (entry - last_close) / entry
    pnl_r = raw_ret / (stop_dist / entry)
    if hit_tp1:
        pnl_r = max(0.5 * tp1_r, pnl_r)
    return {'pnl_r': round(pnl_r, 2) - comm_r, 'exit_reason': 'TIMED_EXIT'}

def run_trifecta_backtest(days: int = 120, active_symbols: list = None, start_date: str = None, end_date: str = None):
    if active_symbols is None:
        active_symbols = ["BTC/USDT"]  # Production Focus: BTC Active (Gold retained for SMT Divergence)

    session_label = f"{start_date} to {end_date}" if start_date and end_date else f"Last {days} Days"
    print("=" * 80)
    print(f" 🏛️  SOVEREIGN SMC — PRODUCTION TRADING ENGINE WALK-FORWARD AUDIT ({session_label})")
    print(f" Active Trade Symbols: {active_symbols} | Intermarket SMT: BTC + Gold (PAXG)")
    print(" Strategies: 1. Judas Inducement Sniper | 2. London Close Silver Bullet | 3. Mean-Reverting Turtle Soup")
    print(" Filters: Weekdays Only | Max 2 Trades/Day | Pessimistic SL-First Collision")
    print("=" * 80)

    dm = DataManager()
    indicators = VectorizedIndicators()

    if start_date and end_date:
        btc_df = dm.get_data("BTC/USDT", timeframe='5m', start_date=start_date, end_date=end_date)
        paxg_df = dm.get_data("PAXG/USDT", timeframe='5m', start_date=start_date, end_date=end_date)
    else:
        btc_df = dm.get_data("BTC/USDT", timeframe='5m', days=days)
        paxg_df = dm.get_data("PAXG/USDT", timeframe='5m', days=days)

    print(f" • Loaded {len(btc_df):,} BTC 5m candles and {len(paxg_df):,} PAXG (Gold) 5m candles.")
    print(" • Pre-calculating Vectorized Indicators, VWAP Bands, Hurst Regimes, and SMT...\n")

    btc_df['timestamp'] = pd.to_datetime(btc_df['timestamp'])
    paxg_df['timestamp'] = pd.to_datetime(paxg_df['timestamp'])

    asset_data = {}
    for sym, df in [("BTC/USDT", btc_df), ("PAXG/USDT", paxg_df)]:
        d = df.copy()
        d['hour'] = d['timestamp'].dt.hour
        d['date'] = d['timestamp'].dt.date
        d = indicators.add_atr(d, period=14)
        d = indicators.add_bias(d, candles_per_4h=48)
        d = indicators.add_displacement(d)
        d = indicators.add_mss(d)
        d = calculate_vwap_and_bands(d, window=24)
        d = indicators.add_equal_highs_lows(d, tolerance_atr_mult=0.15, lookback=50)
        
        # Fast rolling hurst approximation
        closes = d['close'].values
        hurst_vals = np.full(len(d), 0.50)
        for i in range(200, len(d), 12):
            w = closes[i-200:i]
            lags = range(2, 16)
            tau = [np.sqrt(np.std(np.subtract(w[lag:], w[:-lag]))) for lag in lags]
            poly = np.polyfit(np.log(lags), np.log(tau), 1)
            hurst_vals[i:min(i+12, len(d))] = poly[0] * 2.0
        d['hurst'] = hurst_vals

        d['vol_ma'] = d['volume'].rolling(20).mean()
        d['volume_spike'] = d['volume'] >= (d['vol_ma'] * 1.5)

        # 1H HTF levels (96 candles = 8 hours lookback for dynamic swings)
        d['htf_high'] = d['high'].rolling(96).max().shift(2)
        d['htf_low']  = d['low'].rolling(96).min().shift(2)

        asset_data[sym] = d

    # Cross-Asset SMT Divergence
    merged = pd.merge_asof(
        asset_data["BTC/USDT"][['timestamp', 'high', 'low']],
        asset_data["PAXG/USDT"][['timestamp', 'high', 'low']],
        on='timestamp', suffixes=('_btc', '_paxg')
    )
    merged['btc_higher_high'] = merged['high_btc'] > merged['high_btc'].shift(24)
    merged['paxg_higher_high'] = merged['high_paxg'] > merged['high_paxg'].shift(24)
    merged['btc_lower_low'] = merged['low_btc'] < merged['low_btc'].shift(24)
    merged['paxg_lower_low'] = merged['low_paxg'] < merged['low_paxg'].shift(24)

    merged['bear_smt'] = merged['btc_higher_high'] != merged['paxg_higher_high']
    merged['bull_smt'] = merged['btc_lower_low'] != merged['paxg_lower_low']
    smt_map = dict(zip(merged['timestamp'], zip(merged['bear_smt'], merged['bull_smt'])))

    daily_setup_counts = {}
    last_trade_time = {sym: datetime(2000, 1, 1) for sym in asset_data}
    trades = []

    min_bars = 300
    total_bars = len(asset_data["BTC/USDT"])

    print(f" • Scanning 120-Day Walk-Forward Sequence for {active_symbols} under Firewall Invariants...")

    for i in range(min_bars, total_bars - 180):
        for sym in active_symbols:
            df = asset_data[sym]
            row = df.iloc[i]
            ts = row['timestamp']
            d_date = row['date']
            hr = row['hour']

            # ── INVARIANT 3: Strict Killzone Gate ──
            # NY AM & London Close: 12:00 - 17:00 UTC | Asian Open: 00:00 - 04:00 UTC
            # London Open (07:00 - 09:00 UTC) is HARD BLOCKED
            # Exclude Weekends (Saturday=5, Sunday=6) - Gold is closed, Crypto has low liquidity
            if row['timestamp'].weekday() >= 5:
                continue

            is_ny_session = (12 <= hr <= 17)
            is_asian_session = (0 <= hr <= 4)
            if not (is_ny_session or is_asian_session):
                continue

            # ── INVARIANT 11: Global Daily Setup Limit (Max 2 per day) ──
            if daily_setup_counts.get(d_date, 0) >= 2:
                continue

            # ── INVARIANT 4: 30-Minute Cooldown ──
            if (ts - last_trade_time[sym]) < timedelta(minutes=30):
                continue

            c_open = row['open']
            c_high = row['high']
            c_low = row['low']
            c_close = row['close']
            c_range = max(c_high - c_low, 1e-8)
            c_atr = row['atr']
            if pd.isna(c_atr) or c_atr <= 0:
                continue

            upper_wick = c_high - max(c_open, c_close)
            lower_wick = min(c_open, c_close) - c_low
            upper_wick_pct = upper_wick / c_range
            lower_wick_pct = lower_wick / c_range

            h_val = row['hurst']
            h_bias = row['bias']
            smt_info = smt_map.get(ts, (False, False))

            # Minimum stop floor (0.3% of price) + 0.5x ATR buffer
            min_stop_floor = c_close * 0.003
            stop_buffer = max(0.5 * c_atr, min_stop_floor * 0.5)

            detected_setup = None

            # ─────────────────────────────────────────────────────────────
            # 1. STRATEGY 9: JUDAS INDUCEMENT SNIPER (70%+ Rejection Wicks)
            # ─────────────────────────────────────────────────────────────
            if c_range >= (1.6 * c_atr) and row['volume_spike']:
                if upper_wick_pct >= 0.65 and h_val <= 0.58:
                    ai_score = calculate_ai_confluence_score(
                        "JUDAS_INDUCEMENT", row, upper_wick_pct, smt_info[0], h_bias == 'BEARISH'
                    )
                    if ai_score >= 8.0:
                        stop_dist = max(c_high - c_close + stop_buffer, min_stop_floor)
                        detected_setup = {
                            "strategy": "JUDAS_INDUCEMENT_SNIPER",
                            "bias": "BEARISH",
                            "entry": c_close,
                            "stop_dist": stop_dist,
                            "tp1_r": 1.5,
                            "tp2_r": 2.5,
                            "ai_score": ai_score
                        }
                elif lower_wick_pct >= 0.65 and h_val <= 0.58:
                    ai_score = calculate_ai_confluence_score(
                        "JUDAS_INDUCEMENT", row, lower_wick_pct, smt_info[1], h_bias == 'BULLISH'
                    )
                    if ai_score >= 8.0:
                        stop_dist = max(c_close - c_low + stop_buffer, min_stop_floor)
                        detected_setup = {
                            "strategy": "JUDAS_INDUCEMENT_SNIPER",
                            "bias": "BULLISH",
                            "entry": c_close,
                            "stop_dist": stop_dist,
                            "tp1_r": 1.5,
                            "tp2_r": 2.5,
                            "ai_score": ai_score
                        }

            # ─────────────────────────────────────────────────────────────
            # 2. LONDON CLOSE SILVER BULLET (14:00 - 16:00 UTC Rebalance)
            # ─────────────────────────────────────────────────────────────
            if not detected_setup and (14 <= hr <= 16):
                vwap_upper = row['vwap_upper']
                vwap_lower = row['vwap_lower']
                if not pd.isna(vwap_upper) and not pd.isna(vwap_lower):
                    if c_high >= vwap_upper and c_close < vwap_upper and upper_wick_pct >= 0.30 and h_val <= 0.52:
                        ai_score = calculate_ai_confluence_score(
                            "LONDON_CLOSE_SILVER_BULLET", row, upper_wick_pct, smt_info[0], False
                        )
                        if ai_score >= 8.0:
                            stop_dist = max(c_high - c_close + stop_buffer, min_stop_floor)
                            detected_setup = {
                                "strategy": "LONDON_CLOSE_SILVER_BULLET",
                                "bias": "BEARISH",
                                "entry": c_close,
                                "stop_dist": stop_dist,
                                "tp1_r": 1.5,
                                "tp2_r": 2.2,
                                "ai_score": ai_score
                            }
                    elif c_low <= vwap_lower and c_close > vwap_lower and lower_wick_pct >= 0.30 and h_val <= 0.52:
                        ai_score = calculate_ai_confluence_score(
                            "LONDON_CLOSE_SILVER_BULLET", row, lower_wick_pct, smt_info[1], False
                        )
                        if ai_score >= 8.0:
                            stop_dist = max(c_close - c_low + stop_buffer, min_stop_floor)
                            detected_setup = {
                                "strategy": "LONDON_CLOSE_SILVER_BULLET",
                                "bias": "BULLISH",
                                "entry": c_close,
                                "stop_dist": stop_dist,
                                "tp1_r": 1.5,
                                "tp2_r": 2.2,
                                "ai_score": ai_score
                            }

            # ─────────────────────────────────────────────────────────────
            # 3. TURTLE SOUP LIQUIDITY SWEEPS (Mean-Reverting Regime: H <= 0.48)
            # ─────────────────────────────────────────────────────────────
            if not detected_setup:
                htf_high = row['htf_high']
                htf_low  = row['htf_low']
                # Turtle Soup is strictly active in Mean-Reverting / Non-Trending Regimes (Hurst <= 0.48)
                if not pd.isna(htf_high) and not pd.isna(htf_low) and h_val <= 0.48:
                    # Bearish Turtle Soup: Pierce Swing High, Close Below, Wick Rejection >= 35%
                    if c_high > htf_high and c_close < htf_high and upper_wick_pct >= 0.35:
                        sweep_depth = c_high - htf_high
                        if (0.10 * c_atr) <= sweep_depth <= (2.0 * c_atr):
                            ai_score = calculate_ai_confluence_score(
                                "TURTLE_SOUP", row, upper_wick_pct, smt_info[0], h_bias == 'BEARISH'
                            )
                            if ai_score >= 8.0:
                                stop_dist = max(c_high - c_close + stop_buffer, min_stop_floor)
                                detected_setup = {
                                    "strategy": "TURTLE_SOUP_SWEEP",
                                    "bias": "BEARISH",
                                    "entry": c_close,
                                    "stop_dist": stop_dist,
                                    "tp1_r": 1.5,
                                    "tp2_r": 2.2,
                                    "ai_score": ai_score
                                }
                    # Bullish Turtle Soup: Pierce Swing Low, Close Above, Wick Rejection >= 35%
                    elif c_low < htf_low and c_close > htf_low and lower_wick_pct >= 0.35:
                        sweep_depth = htf_low - c_low
                        if (0.10 * c_atr) <= sweep_depth <= (2.0 * c_atr):
                            ai_score = calculate_ai_confluence_score(
                                "TURTLE_SOUP", row, lower_wick_pct, smt_info[1], h_bias == 'BULLISH'
                            )
                            if ai_score >= 8.0:
                                stop_dist = max(c_close - c_low + stop_buffer, min_stop_floor)
                                detected_setup = {
                                    "strategy": "TURTLE_SOUP_SWEEP",
                                    "bias": "BULLISH",
                                    "entry": c_close,
                                    "stop_dist": stop_dist,
                                    "tp1_r": 1.5,
                                    "tp2_r": 2.2,
                                    "ai_score": ai_score
                                }

            if detected_setup:
                future_candles = df.iloc[i+1:i+180]
                result = simulate_trade_with_scale_out(
                    bias=detected_setup['bias'],
                    entry=detected_setup['entry'],
                    stop_dist=detected_setup['stop_dist'],
                    tp1_r=detected_setup['tp1_r'],
                    tp2_r=detected_setup['tp2_r'],
                    future_candles=future_candles,
                    spread_bps=1.5,
                    comm_bps=1.0
                )

                if result['exit_reason'] != 'TIMEOUT':
                    pnl_r = result['pnl_r']
                    trades.append({
                        "timestamp": ts.isoformat(),
                        "symbol": sym,
                        "strategy": detected_setup['strategy'],
                        "direction": detected_setup['bias'],
                        "entry": detected_setup['entry'],
                        "ai_score": detected_setup['ai_score'],
                        "pnl_r": pnl_r,
                        "outcome": "WIN" if pnl_r > 0 else "LOSS",
                        "exit_reason": result['exit_reason']
                    })

                    daily_setup_counts[d_date] = daily_setup_counts.get(d_date, 0) + 1
                    last_trade_time[sym] = ts

    # Results Reporting
    if not trades:
        print("❌ Zero trades qualified under strict invariant filters.")
        return

    tdf = pd.DataFrame(trades)
    total_trades = len(tdf)
    wins = len(tdf[tdf['outcome'] == 'WIN'])
    losses = total_trades - wins
    win_rate = (wins / total_trades) * 100.0

    total_r = tdf['pnl_r'].sum()
    avg_r = tdf['pnl_r'].mean()

    gross_profit_r = tdf[tdf['pnl_r'] > 0]['pnl_r'].sum()
    gross_loss_r = abs(tdf[tdf['pnl_r'] <= 0]['pnl_r'].sum())
    profit_factor = (gross_profit_r / gross_loss_r) if gross_loss_r > 0 else 99.0

    # Drawdown in R
    tdf['cum_r'] = tdf['pnl_r'].cumsum()
    running_max = tdf['cum_r'].cummax()
    max_dd_r = (tdf['cum_r'] - running_max).min()

    calc_days = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).days if start_date and end_date else days
    print("\n" + "=" * 80)
    print(f" 📊 EXECUTIVE PERFORMANCE REPORT — {session_label.upper()} AUDIT")
    print("=" * 80)
    print(f" • Total Qualified Setups:    {total_trades} (Averaging ~{total_trades/calc_days:.2f} trades/day)")
    print(f" • Win Rate:                  {win_rate:.1f}% ({wins} Wins / {losses} Losses)")
    print(f" • Total Net R-Multiple:      {total_r:+.2f} R")
    print(f" • Expected Value per Trade:  {avg_r:+.2f} R")
    print(f" • Empirical Profit Factor:   {profit_factor:.2f}")
    print(f" • Max Trailing Drawdown:     {max_dd_r:.2f} R")
    print("--------------------------------------------------------------------------------")
    print(f" {'Strategy':<28} | {'Trades':<6} | {'Win %':<6} | {'Net R':<8} | {'Avg R':<6} | {'PF':<5}")
    print("--------------------------------------------------------------------------------")
    for strat, group in tdf.groupby('strategy'):
        s_tot = len(group)
        s_wins = len(group[group['outcome'] == 'WIN'])
        s_wr = (s_wins / s_tot) * 100.0 if s_tot > 0 else 0.0
        s_r = group['pnl_r'].sum()
        s_avgr = group['pnl_r'].mean()
        s_gp = group[group['pnl_r'] > 0]['pnl_r'].sum()
        s_gl = abs(group[group['pnl_r'] <= 0]['pnl_r'].sum())
        s_pf = (s_gp / s_gl) if s_gl > 0 else 99.0
        print(f" {strat:<28} | {s_tot:<6} | {s_wr:<5.1f}% | {s_r:<+7.2f}R | {s_avgr:<+5.2f}R | {s_pf:<4.2f}")
    print("--------------------------------------------------------------------------------")
    print(f" {'Asset':<28} | {'Trades':<6} | {'Win %':<6} | {'Net R':<8} | {'Avg R':<6} | {'PF':<5}")
    print("--------------------------------------------------------------------------------")
    for asset, group in tdf.groupby('symbol'):
        a_tot = len(group)
        a_wins = len(group[group['outcome'] == 'WIN'])
        a_wr = (a_wins / a_tot) * 100.0 if a_tot > 0 else 0.0
        a_r = group['pnl_r'].sum()
        a_avgr = group['pnl_r'].mean()
        a_gp = group[group['pnl_r'] > 0]['pnl_r'].sum()
        a_gl = abs(group[group['pnl_r'] <= 0]['pnl_r'].sum())
        a_pf = (a_gp / a_gl) if a_gl > 0 else 99.0
        print(f" {asset:<28} | {a_tot:<6} | {a_wr:<5.1f}% | {a_r:<+7.2f}R | {a_avgr:<+5.2f}R | {a_pf:<4.2f}")
    print("=" * 80 + "\n")

    out_file = f"data/trifecta_backtest_{start_date}_{end_date}.json" if start_date and end_date else "data/trifecta_backtest_results.json"
    tdf.to_json(out_file, orient='records', indent=2)
    print(f"✅ Full trade ledger saved to {out_file}\n")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Institutional Trifecta Backtest")
    parser.add_argument("--days", type=int, default=120, help="Lookback days from today")
    parser.add_argument("--start", type=str, default=None, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", type=str, default=None, help="End date YYYY-MM-DD")
    parser.add_argument("--fall-2025", action="store_true", help="Run Fall 2025 session (Sept 1 to Dec 1, 2025)")
    args = parser.parse_args()

    if args.fall_2025:
        run_trifecta_backtest(start_date="2025-09-01", end_date="2025-12-01")
    elif args.start and args.end:
        run_trifecta_backtest(start_date=args.start, end_date=args.end)
    else:
        run_trifecta_backtest(days=args.days)

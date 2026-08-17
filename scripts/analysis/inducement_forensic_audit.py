import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
from collections import defaultdict

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.engines.inducement_tracker import InducementTracker

def run_inducement_audit():
    print("=" * 80)
    print(" 🕵️ EXTREME OUTLIER & INDUCEMENT FORENSIC AUDIT (STRATEGY 9 RESEARCH)")
    print("=" * 80)

    # 1. Load Raw 60-Day 5m Binance Dataset
    from backtesting.backtest_utils import DataManager
    data_mgr = DataManager()
    print(" • Fetching Raw 5m Historical Candles from Binance (60 Days)...")
    df = data_mgr.get_data("BTC/USDT", timeframe='5m', days=60)
    print(f" • Loaded {len(df)} continuous 5m candles from Binance (BTC/USDT).")

    tracker = InducementTracker(db_path="data/smc_alpha.db")

    events = []
    print(" • Scanning for Extreme Volatility Outliers & Inducement Spikes (>= 2.0x ATR, >= 60% Wick)...")

    # 2. Iterate through candles and detect outliers
    for i in range(30, len(df) - 15):
        event = tracker.detect_outlier_candle(df, idx=i)
        if event:
            # Resolve the outcome using future 12 candles (1 hour)
            res = tracker.resolve_inducements_with_future_data(df, event_id=-1, spike_idx=i, lookahead_bars=12)
            event['resolution'] = res['resolution']
            event['reversal_r'] = res['reversal_r']
            event['spike_idx'] = i
            events.append(event)

    print(f" • Found {len(events)} Extreme Inducement Outliers across 60 Days (~{len(events)/60:.1f} per day).\n")

    if not events:
        print("No events detected.")
        return

    events_df = pd.DataFrame(events)

    # 3. Session Distribution Analysis
    session_counts = events_df['session_tag'].value_counts()
    print("📊 INDUCEMENT FREQUENCY BY SESSION:")
    for session, count in session_counts.items():
        pct = (count / len(events_df)) * 100.0
        print(f"   • {session:<18}: {count:>3} events ({pct:>5.1f}%)")

    # 4. Hourly Heatmap (When do they happen most?)
    hourly_counts = events_df['utc_hour'].value_counts().sort_index()
    print("\n⏰ TOP 5 HOURS FOR INDUCEMENTS (UTC):")
    top_hours = events_df['utc_hour'].value_counts().head(5)
    for hour, count in top_hours.items():
        print(f"   • {hour:02d}:00 UTC: {count} events")

    # 5. Pre-Spike Compression vs Reversal Success
    reversals = events_df[events_df['resolution'] == 'TRUE_INDUCEMENT_REVERSAL']
    breakouts = events_df[events_df['resolution'] == 'BREAKOUT_EXPANSION']
    stalls = events_df[events_df['resolution'] == 'CONSOLIDATION_STALL']

    rev_rate = (len(reversals) / len(events_df)) * 100.0
    brk_rate = (len(breakouts) / len(events_df)) * 100.0
    stl_rate = (len(stalls) / len(events_df)) * 100.0

    print("\n🎯 POST-SPIKE RESOLUTION BREAKDOWN:")
    print(f"   • 🟢 TRUE INDUCEMENT (Violent Reversal): {len(reversals)} ({rev_rate:.1f}%)")
    print(f"   • 🔴 BREAKOUT CONTINUATION (Trend Leg):  {len(breakouts)} ({brk_rate:.1f}%)")
    print(f"   • ⚪ CONSOLIDATION / STALL:             {len(stalls)} ({stl_rate:.1f}%)")

    # 6. SMT Correlation (What happens when SMT is present?)
    high_wick_events = events_df[events_df['upper_wick_pct'].combine(events_df['lower_wick_pct'], max) >= 70.0]
    high_wick_revs = high_wick_events[high_wick_events['resolution'] == 'TRUE_INDUCEMENT_REVERSAL']
    high_wick_wr = (len(high_wick_revs) / len(high_wick_events) * 100.0) if len(high_wick_events) > 0 else 0.0

    print(f"\n💡 KEY ALPHA INSIGHT:")
    print(f"   • When Wick Ratio >= 70.0%, True Reversal Rate rises to: {high_wick_wr:.1f}%")
    print(f"   • Average Reversal Expansion Multiplier: {reversals['reversal_r'].mean():.2f}x Spike Range")

    # 7. Strategy 9: Judas Inducement Hunter Backtest Simulation
    print("\n" + "=" * 80)
    print(" 🚀 STRATEGY 9 ('JUDAS INDUCEMENT HUNTER') SHADOW PERFORMANCE SIMULATION")
    print("=" * 80)

    start_equity = 10000.0
    equity = start_equity
    risk_per_trade = 65.0  # Sized conservatively at $65 risk
    executed_trades = []

    for _, ev in high_wick_events.iterrows():
        is_win = ev['resolution'] == 'TRUE_INDUCEMENT_REVERSAL'
        if is_win:
            # Target 3.0R on clean reversal
            pnl = risk_per_trade * 3.0
        else:
            pnl = -risk_per_trade * 1.05  # -1R + friction

        equity += pnl
        executed_trades.append({'pnl': pnl, 'is_win': is_win})

    strat9_wins = [t for t in executed_trades if t['is_win']]
    strat9_wr = (len(strat9_wins) / len(executed_trades) * 100.0) if len(executed_trades) > 0 else 0.0
    net_gain = equity - start_equity
    ret_pct = (net_gain / start_equity) * 100.0

    print(f"   • Strategy 9 Target: Fades extreme wicks (>=70% wick, >=2.0x ATR) with 3.0R Target")
    print(f"   • Total Trades:      {len(executed_trades)}")
    print(f"   • Win Rate:          {strat9_wr:.1f}%")
    print(f"   • Net Profit ($):    ${net_gain:+,.2f} ({ret_pct:+.1f}%)")
    print(f"   • Profit Factor:     {(len(strat9_wins)*3.0) / (max(1, len(executed_trades)-len(strat9_wins))*1.05):.2f}")
    print("=" * 80)

if __name__ == '__main__':
    run_inducement_audit()

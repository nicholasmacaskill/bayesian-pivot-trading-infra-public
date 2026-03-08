import os
import sys
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Setup minimal logging
logging.basicConfig(level=logging.INFO)

# Load envs
load_dotenv(".env")
load_dotenv(".env.local")

# Add src to path
sys.path.append(os.getcwd())

from src.clients.tl_client import TradeLockerClient

def run_deep_dive(hours_back=720):
    print(f"🕵️  Deep Dive Audit: Analyzing last {hours_back} hours of trading data...")
    
    tl = TradeLockerClient()
    if not tl.helpers:
        print("❌ No TradeLocker credentials found.")
        return

    all_trades = []
    
    for i, helper in enumerate(tl.helpers):
        print(f"📊 Fetching history for Account {i+1} ({helper.email})...")
        trades = helper.get_recent_history(hours=hours_back)
        # Tag each trade with the account email
        for t in trades:
            t['account'] = helper.email
        all_trades.extend(trades)

    if not all_trades:
        print("❌ No trades found in the specified window.")
        return

    df = pd.DataFrame(all_trades)
    df['close_time'] = pd.to_datetime(df['close_time'])
    
    # Basic Metrics
    total_trades = len(df)
    win_trades = df[df['pnl'] > 0]
    loss_trades = df[df['pnl'] < 0]
    breakeven_trades = df[df['pnl'] == 0]
    
    win_rate = (len(win_trades) / total_trades) * 100 if total_trades > 0 else 0
    avg_win = win_trades['pnl'].mean() if not win_trades.empty else 0
    avg_loss = abs(loss_trades['pnl'].mean()) if not loss_trades.empty else 0
    
    # Calculate Expectancy: (WinRate * AvgWin) - (LossRate * AvgLoss)
    win_prob = len(win_trades) / total_trades
    loss_prob = len(loss_trades) / total_trades
    expectancy = (win_prob * avg_win) - (loss_prob * avg_loss)
    
    # Risk-to-Reward (R:R) realized
    rr_realized = avg_win / avg_loss if avg_loss != 0 else 0
    
    # Profit Factor
    gross_profit = win_trades['pnl'].sum()
    gross_loss = abs(loss_trades['pnl'].sum())
    profit_factor = gross_profit / gross_loss if gross_loss != 0 else np.inf

    print("\n" + "="*50)
    print("📈 GLOBAL PERFORMANCE SUMMARY")
    print("="*50)
    print(f"Total Trades:      {total_trades}")
    print(f"Win Rate:          {win_rate:.2f}%")
    print(f"Profit Factor:     {profit_factor:.2f}")
    print(f"Expectancy:        ${expectancy:.2f} per trade")
    print(f"Avg Win:           ${avg_win:.2f}")
    print(f"Avg Loss:          ${avg_loss:.2f}")
    print(f"Realized R:R:      1:{rr_realized:.2f}")
    print("-" * 50)
    
    # Per-Account Deep Dive
    print("\n🏢 PER-ACCOUNT ANALYSIS")
    for acc in df['account'].unique():
        acc_df = df[df['account'] == acc]
        a_wr = (len(acc_df[acc_df['pnl'] > 0]) / len(acc_df)) * 100
        a_pnl = acc_df['pnl'].sum()
        print(f"   Account: {acc}")
        print(f"     Trades: {len(acc_df)} | Win Rate: {a_wr:.2f}% | Total PnL: ${a_pnl:.2f}")
        print(f"     Avg Win: ${acc_df[acc_df['pnl'] > 0]['pnl'].mean():.2f}")
        print(f"     Avg Loss: ${abs(acc_df[acc_df['pnl'] < 0]['pnl'].mean()):.2f}")

    # Session Analysis (UTC)
    df['hour'] = df['close_time'].dt.hour
    def get_session(h):
        if 4 <= h < 7: return "Asian Fade (Prime)"
        if 7 <= h < 11: return "London"
        if 13 <= h < 20: return "New York"
        return "Other"
    
    df['session'] = df['hour'].apply(get_session)
    session_pnl = df.groupby('session')['pnl'].sum()
    session_count = df.groupby('session').size()
    
    print("\n🕒 SESSION PERFORMANCE (UTC)")
    for s in session_pnl.index:
        pnl = session_pnl[s]
        count = session_count[s]
        avg = pnl / count
        print(f"   {s:20}: {count:2} trades | Total PnL: ${pnl:8.2f} | Avg: ${avg:8.2f}")

    # Edge Leakage Check
    print("\n🕵️ EDGE LEAKAGE CHECK")
    max_loss = df['pnl'].min()
    max_win = df['pnl'].max()
    print(f"   Worst Trade: ${max_loss:.2f}")
    print(f"   Best Trade:  ${max_win:.2f}")
    
    # Fat Tail Check: Is one loss wiping out X wins?
    if avg_win > 0:
        multiplier = abs(max_loss) / avg_win
        print(f"   Fat Tail Alert: Worst loss equals {multiplier:.1f} average wins.")
        if multiplier > 3:
            print("   ⚠️  WARNING: Outsized losses are your primary problem. Stop management is weak.")

    if rr_realized < 1.0 and win_rate < 60:
         print("   ⚠️  WARNING: Realized R:R is less than 1:1 with a sub-60% win rate. This is mathematically bankrupt.")

    print("="*50)

if __name__ == "__main__":
    run_deep_dive()

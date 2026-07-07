import os
import sys
import json
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.getcwd())

from src.clients.tl_client import TradeLockerClient
from src.core.supabase_client import SupabaseBridge

def run_performance_audit():
    print("🚀 Starting Bayesian Pivot Performance Audit...")
    load_dotenv(".env")
    load_dotenv(".env.local")
    
    tl = TradeLockerClient()
    sb = SupabaseBridge()
    
    all_trades = []
    
    # 1. Fetch Supabase Journal (Historical Ground Truth)
    print("🛡️ Bayesian Pivot Watchdog starting...")
    try:
        # Fetch last 1000 journal entries
        resp = sb.client.table("journal").select("*").order("timestamp", desc=True).limit(1000).execute()
        sb_trades = resp.data if resp.data else []
        print(f"   ✅ Found {len(sb_trades)} trades in Supabase.")
        for t in sb_trades:
            all_trades.append({
                'id': t.get('trade_id'),
                'symbol': t.get('symbol'),
                'side': t.get('side'),
                'pnl': float(t.get('pnl', 0.0)),
                'timestamp': t.get('timestamp'),
                'source': 'Supabase'
            })
    except Exception as e:
        print(f"   ❌ Supabase Fetch Error: {e}")

    # 2. Fetch TradeLocker History (Live Verification)
    print("🔒 Fetching TradeLocker History (30 Days)...")
    tl_trades = tl.get_recent_history(hours=720) # 30 days
    print(f"   ✅ Found {len(tl_trades)} trades in TradeLocker.")
    
    for t in tl_trades:
        # Avoid duplicates if already in Supabase by trade_id
        if not any(str(at['id']) == str(t['id']) for at in all_trades):
            all_trades.append({
                'id': t['id'],
                'symbol': t['symbol'],
                'side': t['side'],
                'pnl': float(t['pnl']),
                'timestamp': t['close_time'],
                'source': 'TradeLocker'
            })

    if not all_trades:
        print("❌ No trade data found in either source.")
        return

    # 3. Analyze Data
    df = pd.DataFrame(all_trades)
    df['timestamp'] = pd.to_datetime(df['timestamp'], format='ISO8601', utc=True)
    df = df.sort_values('timestamp')
    
    total_trades = len(df)
    wins = df[df['pnl'] > 0]
    losses = df[df['pnl'] < 0]
    breakevens = df[df['pnl'] == 0]
    
    win_rate = (len(wins) / total_trades * 100) if total_trades > 0 else 0
    total_pnl = df['pnl'].sum()
    
    gross_profit = wins['pnl'].sum()
    gross_loss = abs(losses['pnl'].sum())
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')
    
    avg_win = wins['pnl'].mean() if not wins.empty else 0
    avg_loss = abs(losses['pnl'].mean()) if not losses.empty else 0
    risk_reward = (avg_win / avg_loss) if avg_loss > 0 else 0
    
    # Consistency: Trades per day
    df['date'] = df['timestamp'].dt.date
    trades_per_day = df.groupby('date').size()
    avg_trades_per_day = trades_per_day.mean()
    
    # Drawdown Calculation (Assuming unit-based or dollar-based)
    df['cumulative_pnl'] = df['pnl'].cumsum()
    df['peak'] = df['cumulative_pnl'].cummax()
    df['drawdown'] = df['peak'] - df['cumulative_pnl']
    max_drawdown = df['drawdown'].max()
    
    # 4. Result Summary
    results = {
        "metrics": {
            "total_trades": int(total_trades),
            "wins": int(len(wins)),
            "losses": int(len(losses)),
            "breakevens": int(len(breakevens)),
            "win_rate": round(float(win_rate), 2),
            "total_pnl": round(float(total_pnl), 2),
            "profit_factor": round(float(profit_factor), 2),
            "avg_win": round(float(avg_win), 2),
            "avg_loss": round(float(avg_loss), 2),
            "risk_reward": round(float(risk_reward), 2),
            "max_drawdown": round(float(max_drawdown), 2),
            "avg_trades_per_day": round(float(avg_trades_per_day), 2)
        },
        "last_10_pnl": df['pnl'].tail(10).tolist()
    }
    
    print("\n" + "="*40)
    print("📊 PERFORMANCE AUDIT RESULTS")
    print("="*40)
    print(f"Total Trades:      {results['metrics']['total_trades']}")
    print(f"Win Rate:          {results['metrics']['win_rate']}%")
    print(f"Total PnL:         ${results['metrics']['total_pnl']:,.2f}")
    print(f"Profit Factor:     {results['metrics']['profit_factor']}")
    print(f"Avg Win / Loss:    ${results['metrics']['avg_win']:.2f} / ${results['metrics']['avg_loss']:.2f} (R:R: {results['metrics']['risk_reward']:.2f})")
    print(f"Max Drawdown:      ${results['metrics']['max_drawdown']:,.2f}")
    print(f"Consistency:       {results['metrics']['avg_trades_per_day']} trades/day")
    print("="*40)
    
    # Save results for artifact generation
    with open("audit_results.json", "w") as f:
        json.dump(results, f, indent=4)
    print("✅ Results saved to audit_results.json")

if __name__ == "__main__":
    run_performance_audit()

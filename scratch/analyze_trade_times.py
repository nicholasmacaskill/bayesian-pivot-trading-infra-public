import os
import sys
import sqlite3
import pandas as pd
from datetime import datetime

# Add root directory to path
sys.path.append(os.getcwd())

def parse_time(time_str):
    if not time_str:
        return None
    try:
        if str(time_str).isdigit() or (isinstance(time_str, float) and time_str > 1e11):
            return datetime.utcfromtimestamp(float(time_str) / 1000.0)
        return datetime.fromisoformat(time_str.replace('Z', '+00:00')).replace(tzinfo=None)
    except Exception:
        return None

def analyze_times():
    db_path = 'data/smc_alpha.db'
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute("SELECT * FROM journal ORDER BY timestamp ASC")
    trades = [dict(row) for row in c.fetchall()]
    conn.close()
    
    for t in trades:
        t['parsed_date'] = parse_time(t['timestamp'])
        
    trades = [t for t in trades if t['parsed_date'] is not None]
    
    df = pd.DataFrame(trades)
    df['hour_utc'] = df['parsed_date'].dt.hour
    
    # Define sessions (UTC)
    # Asian: 00:00 - 08:00 UTC
    # London: 08:00 - 12:00 UTC (overlaps NY at 12)
    # NY: 12:00 - 20:00 UTC
    # Off-hours: 20:00 - 24:00 UTC
    def get_session(hour):
        if 0 <= hour < 8:
            return 'Asian Session'
        elif 8 <= hour < 12:
            return 'London Session'
        elif 12 <= hour < 20:
            return 'NY Session (AM/PM)'
        else:
            return 'Off-Hours (Sydney/Dead)'

    df['session'] = df['hour_utc'].apply(get_session)
    
    # Filter SYSTEM and ROGUE
    print("=== SESSION PERFORMANCE BREAKDOWN (ALL-TIME) ===")
    
    for strat in ['SYSTEM', 'ROGUE']:
        strat_df = df[df['strategy'] == strat]
        if strat_df.empty:
            continue
            
        print(f"\n--- Strategy: {strat} ---")
        session_stats = []
        for name, group in strat_df.groupby('session'):
            wins = group[group['pnl'] > 0]
            losses = group[group['pnl'] < 0]
            total = len(group)
            win_rate = len(wins) / total * 100 if total > 0 else 0
            total_pnl = group['pnl'].sum()
            
            session_stats.append({
                'Session': name,
                'Trades': total,
                'Win Rate': f"{win_rate:.1f}%",
                'PnL': f"${total_pnl:+.2f}"
            })
            
        print(pd.DataFrame(session_stats).to_string(index=False))
        
    # Analyze by Hour of Day for SYSTEM trades to see peak efficiency hours
    system_df = df[df['strategy'] == 'SYSTEM']
    if not system_df.empty:
        print("\n--- SYSTEM Hourly Performance (Top 5 Best Hours - UTC) ---")
        hourly = system_df.groupby('hour_utc')['pnl'].agg(['count', 'sum']).reset_index()
        hourly.columns = ['Hour (UTC)', 'Trades', 'Net PnL']
        hourly = hourly.sort_values(by='Net PnL', ascending=False)
        print(hourly.head(5).to_string(index=False))
        
        print("\n--- SYSTEM Hourly Performance (Top 5 Worst Hours - UTC) ---")
        hourly_worst = hourly.sort_values(by='Net PnL', ascending=True)
        print(hourly_worst.head(5).to_string(index=False))

if __name__ == '__main__':
    analyze_times()

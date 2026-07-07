import os
import sys
import pandas as pd
from datetime import datetime, timezone

# Add root directory to path
sys.path.append(os.getcwd())

if os.path.exists(".env.local"):
    with open(".env.local", "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

from src.core.supabase_client import SupabaseBridge

def parse_time(time_str):
    if not time_str:
        return None
    try:
        return datetime.fromisoformat(str(time_str).replace('Z', '+00:00')).replace(tzinfo=None)
    except Exception:
        return None

def analyze_supabase():
    sb = SupabaseBridge()
    if not sb.client:
        print("❌ Supabase client failed to initialize.")
        return
        
    print("🔌 Fetching ALL vetted/accepted scans from Supabase...")
    
    limit = 1000
    offset = 0
    all_scans = []
    
    try:
        while True:
            res = sb.client.table("scans")\
                .select("*")\
                .or_("verdict.eq.ACCEPTED,and(verdict.eq.HARD_LOGIC_PASS,ai_score.gte.8.0)")\
                .order("timestamp", desc=False)\
                .range(offset, offset + limit - 1)\
                .execute()
                
            chunk = res.data
            if not chunk:
                break
            
            all_scans.extend(chunk)
            if len(chunk) < limit:
                break
            offset += limit
            
        print(f"Retrieved {len(all_scans)} vetted scans from Supabase.")
        
        df = pd.DataFrame(all_scans)
        df['parsed_time'] = df['timestamp'].apply(parse_time)
        df = df.dropna(subset=['parsed_time'])
        df = df.sort_values(by='parsed_time')
        
        # Group consecutive signals (within 4 hours of the same symbol and pattern/direction)
        distinct_signals = []
        for _, scan in df.iterrows():
            is_duplicate = False
            scan_time = scan['parsed_time']
            scan_dir = str(scan.get('direction') or '').upper()
            
            for logged in distinct_signals:
                if logged['symbol'] == scan['symbol'] and str(logged.get('direction') or '').upper() == scan_dir:
                    time_diff = (scan_time - logged['parsed_time']).total_seconds()
                    if 0 <= time_diff < 14400: # 4 hours
                        is_duplicate = True
                        break
            
            if not is_duplicate:
                distinct_signals.append(scan.to_dict())
                
        df_distinct = pd.DataFrame(distinct_signals)
        print(f"Distinct Trade Opportunities (4H Grouped): {len(df_distinct)}")
        
        print("\n=== OUTCOMES OF DISTINCT HIGH-QUALITY SIGNALS ===")
        print(df_distinct['outcome'].value_counts())
        
        # Filter resolved trades
        resolved = df_distinct[df_distinct['outcome'].isin(['WIN', 'LOSS'])]
        print(f"\nTotal Resolved Distinct Signals: {len(resolved)}")
        
        if len(resolved) > 0:
            win_rate = len(resolved[resolved['outcome'] == 'WIN']) / len(resolved) * 100
            print(f"Win Rate: {win_rate:.2f}%")
            
            # Let's check R-multiple. If actual_r is not logged, we assume 1.48 R for wins, -1.0 R for losses
            # Let's see if actual_r has valid values
            df_distinct['resolved_r'] = df_distinct['actual_r']
            # If actual_r is null, fill with default based on outcome
            df_distinct.loc[(df_distinct['resolved_r'].isna()) & (df_distinct['outcome'] == 'WIN'), 'resolved_r'] = 1.48
            df_distinct.loc[(df_distinct['resolved_r'].isna()) & (df_distinct['outcome'] == 'LOSS'), 'resolved_r'] = -1.00
            df_distinct.loc[~df_distinct['outcome'].isin(['WIN', 'LOSS']), 'resolved_r'] = 0.0
            
            total_r = df_distinct['resolved_r'].sum()
            print(f"Total Net R-Multiple: {total_r:.2f} R")
            print(f"Projected PnL at $200 risk per trade: ${total_r * 200:,.2f}")
            print(f"Projected PnL at $500 risk per trade: ${total_r * 500:,.2f}")
            
            # Let's inspect a sample of recent resolved wins
            wins_sample = df_distinct[df_distinct['outcome'] == 'WIN'].tail(5)
            print("\n=== SAMPLE OF RECENT WINNING SIGNALS ===")
            print(wins_sample[['timestamp', 'symbol', 'pattern', 'outcome', 'resolved_r']].to_string(index=False))
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    analyze_supabase()

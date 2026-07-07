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

def check_performance():
    sb = SupabaseBridge()
    if not sb.client:
        print("❌ Supabase client failed to initialize.")
        return
        
    print("🔌 Fetching resolved scans from today...")
    
    try:
        from datetime import datetime, timedelta, timezone
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        
        res = sb.client.table("scans")\
            .select("*")\
            .gt("resolved_at", cutoff)\
            .execute()
            
        scans = res.data or []
        print(f"Retrieved {len(scans)} resolved scans.")
        
        if not scans:
            print("No resolved scans found in the last 30 minutes.")
            return
            
        df = pd.DataFrame(scans)
        df['parsed_time'] = df['timestamp'].apply(parse_time)
        df = df.dropna(subset=['parsed_time'])
        df = df.sort_values(by='parsed_time')
        
        # Group duplicates within 4 hours
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
        print(f"\nDistinct Trade Opportunities (4H Grouped): {len(df_distinct)}")
        
        print("\n=== Outcome Count for Distinct Opportunities ===")
        print(df_distinct['outcome'].value_counts())
        
        resolved = df_distinct[df_distinct['outcome'].isin(['WIN', 'LOSS'])]
        if not resolved.empty:
            wins = len(resolved[resolved['outcome'] == 'WIN'])
            total = len(resolved)
            win_rate = (wins / total) * 100
            
            # Sum R-multiples (if actual_r is None, fill with defaults)
            resolved['resolved_r'] = resolved['actual_r']
            resolved.loc[(resolved['resolved_r'].isna()) & (resolved['outcome'] == 'WIN'), 'resolved_r'] = 1.48
            resolved.loc[(resolved['resolved_r'].isna()) & (resolved['outcome'] == 'LOSS'), 'resolved_r'] = -1.0
            
            net_r = resolved['resolved_r'].sum()
            
            print(f"\nWin Rate: {win_rate:.2f}%")
            print(f"Net R-multiple: {net_r:.2f} R")
            print(f"PnL at $200 risk per trade: ${net_r * 200:,.2f}")
            print(f"PnL at $500 risk per trade: ${net_r * 500:,.2f}")
            
            print("\n=== Detailed List of Distinct Trades ===")
            print(resolved[['timestamp', 'symbol', 'pattern', 'outcome', 'resolved_r']].to_string(index=False))
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    check_performance()

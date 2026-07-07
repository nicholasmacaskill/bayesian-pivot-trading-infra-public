import os
import sys
import pandas as pd
import numpy as np

sys.path.append(os.getcwd())

if os.path.exists(".env.local"):
    with open(".env.local", "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

from src.core.supabase_client import SupabaseBridge

def count_filtered():
    sb = SupabaseBridge()
    # Fetch ALL scans matching verdict and score
    res = sb.client.table("scans")\
        .select("id,symbol,verdict,ai_score,entry,stop_loss,target,timestamp")\
        .or_("verdict.eq.ACCEPTED,and(verdict.eq.HARD_LOGIC_PASS,ai_score.gte.8.0)")\
        .execute()
        
    df = pd.DataFrame(res.data)
    print(f"Total vetted scans fetched from Supabase: {len(df)}")
    
    if not df.empty:
        df_valid = df.dropna(subset=['entry', 'stop_loss', 'target'])
        print(f"Vetted scans with non-null entries: {len(df_valid)}")
        
        # Group duplicates within 4 hours
        df_valid['parsed_time'] = pd.to_datetime(df_valid['timestamp'], utc=True).dt.tz_localize(None)
        df_valid = df_valid.sort_values(by='parsed_time')
        
        distinct_signals = []
        for _, scan in df_valid.iterrows():
            is_duplicate = False
            scan_time = scan['parsed_time']
            scan_dir = str(scan.get('direction') or scan.get('bias') or '').upper()
            
            for logged in distinct_signals:
                if logged['symbol'] == scan['symbol'] and str(logged.get('direction') or logged.get('bias') or '').upper() == scan_dir:
                    time_diff = (scan_time - logged['parsed_time']).total_seconds()
                    if 0 <= time_diff < 14400: # 4 hours
                        is_duplicate = True
                        break
            
            if not is_duplicate:
                distinct_signals.append(scan.to_dict())
                
        df_distinct = pd.DataFrame(distinct_signals)
        print(f"Distinct vetted trade opportunities (4H grouped): {len(df_distinct)}")

if __name__ == '__main__':
    count_filtered()

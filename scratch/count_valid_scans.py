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

def count_scans():
    sb = SupabaseBridge()
    # Fetch all scans with non-null entry
    res = sb.client.table("scans")\
        .select("id,symbol,verdict,ai_score,entry,stop_loss,target,timestamp")\
        .not_.is_("entry", "null")\
        .execute()
        
    df = pd.DataFrame(res.data)
    print(f"Total scans with non-null entry in Supabase: {len(df)}")
    if not df.empty:
        print("\n=== Verdict distribution for scans with entries ===")
        print(df['verdict'].value_counts())
        
        print("\n=== Sample of scans with entries ===")
        print(df.head(5).to_string(index=False))

if __name__ == '__main__':
    count_scans()

import os
import sys
import pandas as pd

sys.path.append(os.getcwd())

if os.path.exists(".env.local"):
    with open(".env.local", "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

from src.core.supabase_client import SupabaseBridge

def inspect():
    sb = SupabaseBridge()
    res = sb.client.table("scans")\
        .select("id,symbol,verdict,ai_score,entry,stop_loss,target,timestamp")\
        .not_.is_("entry", "null")\
        .execute()
        
    df = pd.DataFrame(res.data)
    if df.empty:
        print("No scans found.")
        return
        
    print(f"Total scans with non-null entries: {len(df)}")
    print("\n=== Verdict distribution for scans with entries ===")
    print(df['verdict'].value_counts())
    
    print("\n=== AI Score distribution for HARD_LOGIC_PASS scans with entries ===")
    df_hlp = df[df['verdict'] == 'HARD_LOGIC_PASS']
    print(df_hlp['ai_score'].value_counts())
    
    df_accepted = df[df['verdict'] == 'ACCEPTED']
    print(f"\nTotal ACCEPTED scans: {len(df_accepted)}")
    
    df_high_score = df[(df['verdict'] == 'HARD_LOGIC_PASS') & (df['ai_score'] >= 8.0)]
    print(f"Total HARD_LOGIC_PASS scans with AI Score >= 8: {len(df_high_score)}")

if __name__ == '__main__':
    inspect()

import sqlite3
import pandas as pd

def check_months():
    conn = sqlite3.connect('data/smc_alpha.db')
    
    # Load all scans
    df = pd.read_sql_query("SELECT timestamp FROM scans", conn)
    conn.close()
    
    # Parse months
    def extract_month(ts):
        if not ts: return 'Unknown'
        ts_str = str(ts)
        if ts_str.isdigit():
            # Unix epoch
            return datetime.utcfromtimestamp(float(ts_str)/1000.0).strftime('%Y-%m')
        # ISO string
        return ts_str[:7]
        
    df['month'] = df['timestamp'].apply(extract_month)
    print("=== Scans Count by Month ===")
    print(df['month'].value_counts())

if __name__ == '__main__':
    from datetime import datetime
    check_months()

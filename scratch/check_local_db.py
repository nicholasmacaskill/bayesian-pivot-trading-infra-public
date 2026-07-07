import sqlite3
import pandas as pd

def check_local_db():
    conn = sqlite3.connect('data/smc_alpha.db')
    df_scans = pd.read_sql_query("SELECT verdict, COUNT(*) as count FROM scans GROUP BY verdict", conn)
    print("=== Verdict counts in local SQLite scans table ===")
    print(df_scans.to_string(index=False))
    
    # Also check if there are non-null entry columns
    df_entries = pd.read_sql_query("SELECT COUNT(*) as count FROM scans WHERE entry IS NOT NULL", conn)
    print(f"\nScans with non-null entry in local SQLite: {df_entries.iloc[0]['count']}")
    
    conn.close()

if __name__ == '__main__':
    check_local_db()

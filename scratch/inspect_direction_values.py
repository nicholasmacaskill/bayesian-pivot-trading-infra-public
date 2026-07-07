import sqlite3
import pandas as pd

def inspect_direction():
    conn = sqlite3.connect('data/smc_alpha.db')
    
    df_scans = pd.read_sql_query("SELECT DISTINCT direction FROM scans", conn)
    print("=== Scans Directions ===")
    print(df_scans)
    
    # Check a few accepted scans to see direction/bias
    df_acc_scans = pd.read_sql_query("SELECT timestamp, symbol, direction, bias, verdict FROM scans WHERE verdict='ACCEPTED' LIMIT 10", conn)
    print("\n=== Sample ACCEPTED Scans ===")
    print(df_acc_scans)
    
    # Check why a specific trade didn't match. For example, trade at timestamp 1773136555000 (BTC/USD BUY)
    # 1773136555000 / 1000 = 1773136555 (2026-03-10 12:35:55 UTC)
    # Let's search scans around 2026-03-10 12:35:55 UTC (between 12:05:00 and 13:05:00)
    df_match = pd.read_sql_query("SELECT timestamp, symbol, direction, bias, verdict FROM scans WHERE symbol='BTC/USD' AND timestamp LIKE '2026-03-10T12%'", conn)
    print("\n=== Scans on 2026-03-10 between 12:00 and 13:00 UTC ===")
    print(df_match)
    
    conn.close()

if __name__ == '__main__':
    inspect_direction()

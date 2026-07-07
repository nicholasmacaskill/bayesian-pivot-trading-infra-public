import sqlite3
import pandas as pd

def check_ranges():
    conn = sqlite3.connect('data/smc_alpha.db')
    
    df_journal = pd.read_sql_query("SELECT MIN(timestamp), MAX(timestamp), COUNT(*) FROM journal", conn)
    df_scans = pd.read_sql_query("SELECT MIN(timestamp), MAX(timestamp), COUNT(*) FROM scans", conn)
    df_scans_accepted = pd.read_sql_query("SELECT MIN(timestamp), MAX(timestamp), COUNT(*) FROM scans WHERE verdict='ACCEPTED'", conn)
    
    conn.close()
    
    print("=== JOURNAL TIMESTAMP RANGE ===")
    print(df_journal)
    
    print("\n=== ALL SCANS TIMESTAMP RANGE ===")
    print(df_scans)
    
    print("\n=== ACCEPTED SCANS TIMESTAMP RANGE ===")
    print(df_scans_accepted)

if __name__ == '__main__':
    check_ranges()

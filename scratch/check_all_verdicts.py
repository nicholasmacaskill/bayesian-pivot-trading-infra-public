import sqlite3
import pandas as pd

def check_all_verdicts():
    conn = sqlite3.connect('data/smc_alpha.db')
    
    df = pd.read_sql_query("SELECT verdict, count(*) FROM scans GROUP BY verdict", conn)
    print("=== Unique Verdicts (All-Time) ===")
    print(df)
    
    conn.close()

if __name__ == '__main__':
    check_all_verdicts()

import sqlite3
import pandas as pd

def check_verdicts():
    conn = sqlite3.connect('data/smc_alpha.db')
    
    # Load all scans since April 8
    df = pd.read_sql_query("SELECT verdict, count(*) FROM scans WHERE timestamp >= '2026-04-08' GROUP BY verdict", conn)
    print("=== Verdict counts since 2026-04-08 ===")
    print(df)
    
    # Let's check a sample of recent scans with high ai_score
    df_high = pd.read_sql_query("SELECT timestamp, symbol, pattern, bias, ai_score, verdict FROM scans WHERE timestamp >= '2026-06-01' AND ai_score >= 8.0 ORDER BY timestamp DESC LIMIT 10", conn)
    print("\n=== Recent High AI Score Scans (Since June 1st) ===")
    print(df_high.to_string())
    
    conn.close()

if __name__ == '__main__':
    check_verdicts()

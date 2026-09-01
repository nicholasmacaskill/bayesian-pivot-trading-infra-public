import sys
import os
import time
import sqlite3
import pandas as pd
from datetime import datetime, timezone

sys.path.append(os.getcwd())
from src.clients.tl_client import TradeLockerClient

def main():
    tl = TradeLockerClient()
    print("==========================================================================")
    print("        DEEP DIVE: ALL CLOSED TRADES ON SUNDAY (AUG 30) ACROSS FLEET       ")
    print("==========================================================================")
    
    all_today_trades = []
    
    for i, helper in enumerate(tl.helpers):
        try:
            if i > 0:
                time.sleep(2.0)
            helper.login()
            trades = helper.get_recent_history(hours=36)
            for t in trades:
                # Filter for Aug 30
                close_time = t.get('close_time', '')
                if '2026-08-30' in close_time:
                    t['account'] = f"Account {i+1}"
                    t['account_email'] = helper.email
                    all_today_trades.append(t)
        except Exception as e:
            print(f"Error reading Account {i+1}: {e}")
            
    if all_today_trades:
        df = pd.DataFrame(all_today_trades)
        print(f"\nTotal Trades Closed on Aug 30: {len(df)}")
        print(df[['account', 'id', 'symbol', 'side', 'entry_price', 'price', 'qty', 'pnl', 'close_time']].to_string(index=False))
        
        print("\n--- SUMMARY BY SYMBOL ---")
        print(df.groupby(['symbol', 'side']).agg({'pnl': ['count', 'sum', 'mean']}))
    else:
        print("\nNo trades closed on 2026-08-30 found.")
        
    print("\n==========================================================================")
    print("                   DATABASE SIGNALS AROUND THOSE TIMES                    ")
    print("==========================================================================")
    conn = sqlite3.connect("data/smc_alpha.db")
    df_scans = pd.read_sql_query("""
        SELECT timestamp, symbol, pattern, direction, ai_score, verdict, formations
        FROM scans
        WHERE timestamp >= '2026-08-30' AND pattern NOT LIKE '%HEARTBEAT%'
        ORDER BY rowid DESC LIMIT 15
    """, conn)
    print(df_scans.to_string())
    conn.close()

if __name__ == "__main__":
    main()

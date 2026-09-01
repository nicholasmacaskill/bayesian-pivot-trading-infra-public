import sys
import os
import time
import sqlite3
import pandas as pd
from datetime import datetime, timezone

sys.path.append(os.getcwd())
from src.clients.tl_client import TradeLockerClient

def main():
    print("==========================================================================")
    print("                 LIVE FLEET POSITION & SIGNAL AUDIT                       ")
    print("==========================================================================")
    
    tl = TradeLockerClient()
    total_open = 0
    
    for i, helper in enumerate(tl.helpers):
        try:
            if i > 0:
                time.sleep(2.0)
            helper.login()
            helper.get_account_details()
            bal = getattr(helper, "balance", 0.0)
            positions = helper.get_open_positions()
            total_open += len(positions)
            print(f"\nAccount {i+1} ({helper.email}): Equity=${bal:,.2f} | Open Positions={len(positions)}")
            for p in positions:
                pos_id = p.get('id')
                sym = p.get('symbol')
                side = p.get('side')
                qty = p.get('qty')
                price = p.get('price')
                sl = p.get('stopLoss')
                tp = p.get('takeProfit')
                pnl = float(p.get('unrealizedPl', 0.0))
                print(f"   [OPEN TRADE] ID: {pos_id} | {sym} {side.upper()} {qty} lots @ {price} | SL: {sl} | TP: {tp} | Live PnL: ${pnl:,.2f}")
                
            history = helper.get_recent_history(hours=6)
            if history:
                print(f"   [RECENT CLOSED TRADES (Last 6 Hours)] ({len(history)} trades):")
                for h in history:
                    h_id = h.get('id')
                    h_side = h.get('side')
                    h_pnl = h.get('pnl')
                    h_price = h.get('price')
                    h_time = h.get('close_time')
                    print(f"      -> ID: {h_id} | {h_side} @ {h_price} | PnL: ${h_pnl:,.2f} | Closed: {h_time}")
        except Exception as e:
            print(f"Account {i+1} error: {e}")
            
    print(f"\nTotal Active Positions Across Entire Fleet: {total_open}")
    
    print("\n==========================================================================")
    print("                     RECENT SIGNED LEDGER ENTRIES                         ")
    print("==========================================================================")
    conn = sqlite3.connect("data/smc_alpha.db")
    try:
        df_ledger = pd.read_sql_query("""
            SELECT timestamp, symbol, direction, pattern, ai_score, outcome, pnl
            FROM signed_ledger
            ORDER BY rowid DESC LIMIT 10
        """, conn)
        print(df_ledger.to_string())
    except Exception as e:
        print("Ledger error:", e)
        
    print("\n==========================================================================")
    print("                       RECENT LIVE MARKET SCANS                           ")
    print("==========================================================================")
    try:
        df_scans = pd.read_sql_query("""
            SELECT timestamp, symbol, pattern, direction, ai_score, verdict, formations
            FROM scans
            WHERE pattern NOT LIKE '%HEARTBEAT%'
            ORDER BY rowid DESC LIMIT 10
        """, conn)
        print(df_scans.to_string())
    except Exception as e:
        print("Scans error:", e)
        
    conn.close()

if __name__ == "__main__":
    main()

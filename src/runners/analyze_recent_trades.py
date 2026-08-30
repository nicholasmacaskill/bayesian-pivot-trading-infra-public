import sys
import os
import sqlite3
import pandas as pd
from datetime import datetime, timezone

sys.path.append(os.getcwd())
from src.clients.tl_client import TradeLockerClient

def main():
    print("==================================================")
    print("        FULL FLEET LIVE EXECUTION AUDIT          ")
    print("==================================================")
    
    tl = TradeLockerClient()
    
    total_fleet_equity = 0.0
    open_positions_total = 0
    
    for i, helper in enumerate(tl.helpers):
        try:
            if i > 0:
                time.sleep(2.0)
            helper.login()
            helper.get_account_details()
            balance = getattr(helper, "balance", 0.0)
            total_fleet_equity += balance
            positions = helper.get_open_positions()
            open_positions_total += len(positions)
            
            print(f"\nAccount {i+1} ({helper.email}): Equity = ${balance:,.2f} | Open Positions = {len(positions)}")
            for p in positions:
                pos_id = p.get('id')
                sym = p.get('symbol')
                side = p.get('side')
                qty = p.get('qty')
                price = p.get('price')
                sl = p.get('stopLoss')
                tp = p.get('takeProfit')
                pnl = float(p.get('unrealizedPl', 0.0))
                print(f"   [OPEN] ID: {pos_id} | {sym} {side.upper()} {qty} lots @ {price} | SL: {sl} | TP: {tp} | Live PnL: ${pnl:,.2f}")
                
            history = helper.get_recent_history(24)
            if history:
                print(f"   [RECENT CLOSED TRADES] (Last 24h: {len(history)} trades):")
                for h in history[-3:]:
                    h_id = h.get('id')
                    h_side = h.get('side')
                    h_pnl = h.get('pnl')
                    h_price = h.get('price')
                    h_time = h.get('close_time')
                    print(f"      -> ID: {h_id} | {h_side} @ {h_price} | PnL: ${h_pnl:,.2f} | Closed: {h_time}")
        except Exception as e:
            print(f"Account {i+1} audit error: {e}")
            
    print("\n--------------------------------------------------")
    print(f"TOTAL FLEET EQUITY: ${total_fleet_equity:,.2f} across 8 accounts")
    print(f"TOTAL ACTIVE POSITIONS: {open_positions_total}")
    print("--------------------------------------------------")
    
    print("\n==================================================")
    print("          RECENT DATABASE SCANS & SIGNALS        ")
    print("==================================================")
    conn = sqlite3.connect("data/smc_alpha.db")
    df_scans = pd.read_sql_query("""
        SELECT timestamp, symbol, pattern, direction, ai_score, verdict, formations
        FROM scans
        WHERE pattern NOT LIKE '%HEARTBEAT%'
        ORDER BY rowid DESC LIMIT 10
    """, conn)
    print(df_scans.to_string())
    
    print("\n==================================================")
    print("           RECENT COUNTERFACTUAL TRADES           ")
    print("==================================================")
    try:
        df_cf = pd.read_sql_query("""
            SELECT id, timestamp, symbol, direction, pattern, entry_price, stop_loss, take_profit_1, status, outcome, simulated_pnl, simulated_r, rejection_reasons
            FROM counterfactual_trades
            ORDER BY rowid DESC LIMIT 6
        """, conn)
        print(df_cf.to_string())
    except Exception as e:
        print("CF Query Error:", e)
        
    conn.close()

if __name__ == "__main__":
    main()

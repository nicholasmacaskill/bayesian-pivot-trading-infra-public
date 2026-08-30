import sys
import os
import time
sys.path.append(os.getcwd())
from src.clients.tl_client import TradeLockerClient

def main():
    tl = TradeLockerClient()
    print("==================================================")
    print("      LAST 24 HOURS EXACT BROKER PNL AUDIT        ")
    print("==================================================")
    
    total_fleet_24h_pnl = 0.0
    total_trades_count = 0
    
    for i, helper in enumerate(tl.helpers):
        try:
            if i > 0:
                time.sleep(2.0)
            helper.login()
            helper.get_account_details()
            trades = helper.get_recent_history(hours=24)
            acct_pnl = sum(t.get('pnl', 0.0) for t in trades)
            total_fleet_24h_pnl += acct_pnl
            total_trades_count += len(trades)
            
            status_str = f"+${acct_pnl:,.2f}" if acct_pnl >= 0 else f"-${abs(acct_pnl):,.2f}"
            print(f"Account {i+1} ({helper.email}): {len(trades)} trades | 24h PnL = {status_str}")
            for t in trades:
                side = t.get('side')
                pnl = t.get('pnl')
                price = t.get('price')
                time_str = t.get('close_time')
                pnl_disp = f"+${pnl:,.2f}" if pnl >= 0 else f"-${abs(pnl):,.2f}"
                print(f"   -> {side} @ {price} | PnL: {pnl_disp} | Closed: {time_str}")
        except Exception as e:
            print(f"Account {i+1} audit error: {e}")

    print("\n--------------------------------------------------")
    overall_str = f"+${total_fleet_24h_pnl:,.2f} NET PROFIT" if total_fleet_24h_pnl >= 0 else f"-${abs(total_fleet_24h_pnl):,.2f} NET LOSS"
    print(f"TOTAL FLEET 24H RESULT: {overall_str} across {total_trades_count} closed trades")
    print("--------------------------------------------------")

if __name__ == "__main__":
    main()

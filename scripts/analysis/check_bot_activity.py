import os
from dotenv import load_dotenv
from tl_client import TradeLockerClient

# Load env vars first
load_dotenv(".env.local")

def check_activity():
    print("Checking TradeLocker Activity...")
    try:
        tl = TradeLockerClient()
        
        # Check Equity
        equity = tl.get_total_equity()
        print(f"Total Equity: ${equity:,.2f}")
        
        # Check Open Positions
        open_positions = tl.get_open_positions()
        print(f"Open Positions: {len(open_positions)}")
        for p in open_positions:
            print(f" - [OPEN] {p['symbol']} {p['side']} (PnL: {p['pnl']})")
            
        # Check History (Last 24h)
        history = tl.get_recent_history(hours=24)
        print(f"Trades in last 24h: {len(history)}")
        for h in history:
            print(f" - [CLOSED] {h['symbol']} {h['side']} (PnL: {h['pnl']}) at {h['close_time']}")
            
    except Exception as e:
        print(f"Error checking activity: {e}")

if __name__ == "__main__":
    check_activity()

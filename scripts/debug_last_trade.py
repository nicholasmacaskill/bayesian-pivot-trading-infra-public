import os
import sys
from datetime import datetime, timedelta

# Add src to path
sys.path.append(os.getcwd())

from src.clients.tl_client import TradeLockerClient
from dotenv import load_dotenv

def find_last_trade():
    print("🔍 Searching for the absolute last TradeLocker trade (7-day window)...")
    load_dotenv(".env")
    load_dotenv(".env.local")
    tl = TradeLockerClient()
    
    for i, helper in enumerate(tl.helpers):
        print(f"\n--- Account {i+1} ({helper.email}) ---")
        if not helper.access_token:
            if not helper.login(): continue
            
        history = helper.get_recent_history(hours=168) # 7 days
        if not history:
            print("   No trades found in the last 7 days.")
            continue
            
        # Sort by close time descending
        try:
            # Handle potential Z or other T formats
            history.sort(key=lambda x: x['close_time'], reverse=True)
        except: pass
            
        print(f"   Found {len(history)} trades in last 7 days. Most recent:")
        for t in history[:5]:
            print(f"   - ID: {t['id']} | {t['symbol']} {t['side']} | PnL: ${t['pnl']:.2f} | Closed: {t['close_time']}")

if __name__ == "__main__":
    find_last_trade()

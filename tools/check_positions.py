import sys
import os
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

from src.clients.tl_client import TradeLockerClient

def check_live_positions():
    print("🚀 Connecting to TradeLocker...")
    client = TradeLockerClient()
    
    positions = client.get_open_positions()
    
    if not positions:
        print("📭 No open positions found.")
    else:
        print(f"✅ Found {len(positions)} open positions:\n")
        for p in positions:
            print(f"🔹 {p['symbol']} {p['side']}")
            print(f"   ID: {p['id']}")
            print(f"   Entry: {p['price']}")
            print(f"   Current PnL: ${p['pnl']:,.2f}")
            print(f"   Status: {p['status']}")
            print("-" * 20)

    # Also check recent history to see if it just closed
    print("\n📜 Checking recent history (last 4h)...")
    history = client.get_recent_history(hours=4)
    if not history:
        print("📭 No recently closed trades.")
    else:
        for p in history:
            print(f"🔸 {p['symbol']} {p['side']} (CLOSED)")
            print(f"   PnL: ${p['pnl']:,.2f}")
            print(f"   Close Price: {p['price']}")
            print("-" * 20)

if __name__ == "__main__":
    check_live_positions()

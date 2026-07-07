import os
import sys
import logging
from dotenv import load_dotenv

# Setup minimal logging
logging.basicConfig(level=logging.INFO)

# Load envs
load_dotenv(".env")
load_dotenv(".env.local")

# Add src to path
sys.path.append(os.getcwd())

from src.clients.tl_client import TradeLockerClient

def verify_tradelocker():
    print("🔌 Testing TradeLocker Connectivity...")
    
    try:
        tl = TradeLockerClient()
        if not tl.helpers:
            print("❌ No TradeLocker credentials found in .env.local")
            return

        print(f"✅ Found {len(tl.helpers)} account(s) configured.")
        
        # Test History Fetch
        print("📜 Fetching recent history (24h)...")
        history = tl.get_recent_history(hours=24)
        print(f"   Fetched {len(history)} trades.")
        for t in history[:3]:
            print(f"   - {t['symbol']} {t['side']} PnL: ${t['pnl']:.2f}")

        # Test Open Positions
        print("📈 Fetching open positions...")
        positions = tl.get_open_positions()
        print(f"   Found {len(positions)} open positions.")
        for p in positions:
            print(f"   - {p['symbol']} {p['side']} Entry: {p['price']}")

    except Exception as e:
        print(f"❌ TradeLocker Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_tradelocker()

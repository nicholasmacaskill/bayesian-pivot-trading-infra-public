import os
import sys
from dotenv import load_dotenv

# Add root to sys.path
sys.path.append(os.getcwd())

from src.clients.tl_client import TradeLockerClient

def check_live_positions():
    load_dotenv(".env.local")
    tl = TradeLockerClient()
    
    print("Fetching live positions from TradeLocker...")
    try:
        positions = tl.get_open_positions()
        if not positions:
            print("No open positions found.")
            return
            
        print("-" * 50)
        for pos in positions:
            print(f"ID: {pos['id']}")
            print(f"Symbol: {pos['symbol']}")
            print(f"Side: {pos['side']}")
            print(f"Quantity: {pos['qty']}")
            print(f"Entry Price: {pos['price']}")
            print(f"Current PnL: ${pos['pnl']}")
            print("-" * 50)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_live_positions()

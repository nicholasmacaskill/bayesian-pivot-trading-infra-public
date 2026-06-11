import os
import sys
from dotenv import load_dotenv

# Add the project root to sys.path
sys.path.append(os.getcwd())

from src.clients.tl_client import TradeLockerClient

def main():
    load_dotenv('.env.local')
    client = TradeLockerClient()
    positions = client.get_open_positions()
    
    if not positions:
        print("No open positions found.")
        return

    print(f"Found {len(positions)} open positions:")
    for p in positions:
        print(f"- {p['side']} {p['qty']} {p['symbol']} at {p['price']} (PnL: {p['pnl']})")

if __name__ == '__main__':
    main()

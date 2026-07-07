import sys
import os
from dotenv import load_dotenv

sys.path.append(os.getcwd())
from src.clients.tl_client import TradeLockerClient

def check():
    load_dotenv('.env.local')
    tl = TradeLockerClient()
    total = tl.get_total_equity()
    print(f"Total Equity across all accounts: ${total:,.2f}")

if __name__ == "__main__":
    check()

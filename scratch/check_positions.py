import sys
import os
from dotenv import load_dotenv

sys.path.append(os.getcwd())
from src.clients.tl_client import TradeLockerClient

def check():
    load_dotenv('.env.local')
    tl = TradeLockerClient()
    positions = tl.get_open_positions()
    print("OPEN POSITIONS:")
    for p in positions:
        print(p)

if __name__ == "__main__":
    check()

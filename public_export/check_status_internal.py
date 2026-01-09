import os
from tradelocker_client import TradeLockerClient

def check_status():
    try:
        tl = TradeLockerClient()
        equity = tl.get_total_equity()
        trades_today = tl.get_daily_trades_count()
        print(f"EQUITY: {equity}")
        print(f"TRADES_TODAY: {trades_today}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    check_status()

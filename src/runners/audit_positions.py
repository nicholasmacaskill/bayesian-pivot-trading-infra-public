import sys
import os
sys.path.append(os.getcwd())

from src.clients.tl_client import TradeLockerClient

def main():
    tl = TradeLockerClient()
    print("=== TRADELOCKER LIVE POSITION & RISK AUDIT ===")

    for i, h in enumerate(tl.helpers):
        try:
            h.login()
            pos = h.get_open_positions()
            tot_qty = sum(float(p.get('qty', 0)) for p in pos)
            print(f"Account {i+1} ({h.email}): Balance=${h.balance:.2f} | Open Pos={len(pos)} | Total Lots={tot_qty}")
            for p in pos:
                print(f"   -> ID={p.get('id')} | Side={p.get('side')} | Qty={p.get('qty')} | Price={p.get('price')} | PnL=${p.get('pnl')}")
        except Exception as e:
            print(f"Account {i+1} error: {e}")

if __name__ == "__main__":
    main()

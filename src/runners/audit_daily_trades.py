import sys
import os
sys.path.append(os.getcwd())

from datetime import datetime
from src.clients.tl_client import TradeLockerClient

def main():
    tl = TradeLockerClient()
    print("=== EXACT DAILY TRADES & PNL AUDIT (TODAY ONLY) ===")

    for i, h in enumerate(tl.helpers):
        try:
            h.login()
            trades = h.get_recent_history(hours=24)
            # Filter trades closed today (2026-08-28)
            today_str = datetime.utcnow().strftime("%Y-%m-%d")
            today_trades = [t for t in trades if t.get('close_time', '').startswith(today_str)]
            
            today_pnl = sum(float(t.get('pnl', 0.0)) for t in today_trades)
            print(f"\nAccount {i+1} ({h.email}): {len(today_trades)} closed trade(s) today | Net Closed Today: ${today_pnl:+.2f}")
            for t in today_trades:
                side = t.get('side')
                qty = t.get('qty')
                sym = t.get('symbol')
                pnl = t.get('pnl')
                close_t = t.get('close_time')
                print(f"   -> {side} {qty} {sym} | PnL: ${pnl:+.2f} | Time: {close_t}")
        except Exception as e:
            print(f"Account {i+1} error: {e}")

if __name__ == "__main__":
    main()

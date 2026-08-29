import sys
import os
sys.path.append(os.getcwd())

import time
from src.clients.tl_client import TradeLockerClient

def main():
    tl = TradeLockerClient()
    target_sl = 2492.00
    target_tp = 2533.00

    print("=== UPDATING FLEET STOP LOSS TO 2492.00 IN PLACE ===")

    success_count = 0
    total_positions = 0

    for i, h in enumerate(tl.helpers):
        try:
            positions = h.get_open_positions()
            print(f"Account {i+1} ({h.email}): {len(positions)} positions found")
            for p in positions:
                pos_id = p.get('id')
                total_positions += 1
                print(f"   -> Updating Position {pos_id} to SL={target_sl}, TP={target_tp}...")
                res = h.modify_position_bracket(pos_id, stop_loss=target_sl, take_profit=target_tp)
                if res:
                    success_count += 1
                    print(f"      ✅ Success: Position {pos_id} updated.")
                else:
                    print(f"      ❌ Warning: Position {pos_id} update failed.")
                time.sleep(1.0)
        except Exception as e:
            print(f"Account {i+1} error: {e}")
        time.sleep(2.5)

    print("\n=== POST-EXECUTION RECONCILIATION AUDIT ===")
    verified_count = 0
    for i, h in enumerate(tl.helpers):
        try:
            positions = h.get_open_positions()
            print(f"Account {i+1} ({h.email}):")
            for p in positions:
                sl = p.get('stopLoss')
                tp = p.get('takeProfit')
                pos_id = p.get('id')
                qty = p.get('qty')
                print(f"   -> POS {pos_id} | Qty: {qty} | SL: {sl} | TP: {tp}")
                if sl == target_sl or sl == float(target_sl):
                    verified_count += 1
        except Exception as e:
            print(f"Account {i+1} audit error: {e}")

    print(f"\nAudit Summary: {verified_count}/{total_positions} positions verified with SL={target_sl}!")

if __name__ == "__main__":
    main()

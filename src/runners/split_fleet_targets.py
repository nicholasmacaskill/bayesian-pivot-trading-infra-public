import sys
import os
sys.path.append(os.getcwd())

import time
from src.clients.tl_client import TradeLockerClient

def main():
    tl = TradeLockerClient()
    sl_level = 2492.00
    tp1_level = 2533.00
    tp2_level = 2560.00

    print("=== CONFIGURING SPLIT TARGETS (TP1: $2,533 | TP2: $2,560) ACROSS FLEET ===")

    for i, h in enumerate(tl.helpers):
        try:
            h.login()
            positions = h.get_open_positions()
            print(f"Account {i+1} ({h.email}): {len(positions)} position(s) found")
            
            if len(positions) >= 2:
                # Ticket 1 -> TP1: 2533.00
                pos1_id = positions[0].get('id')
                res1 = h.modify_position_bracket(pos1_id, stop_loss=sl_level, take_profit=tp1_level)
                print(f"  -> Ticket 1 ({pos1_id}): SL={sl_level}, TP={tp1_level} -> Success: {res1}")
                time.sleep(1.0)

                # Ticket 2 -> TP2: 2560.00
                pos2_id = positions[1].get('id')
                res2 = h.modify_position_bracket(pos2_id, stop_loss=sl_level, take_profit=tp2_level)
                print(f"  -> Ticket 2 ({pos2_id}): SL={sl_level}, TP={tp2_level} -> Success: {res2}")
            elif len(positions) == 1:
                pos_id = positions[0].get('id')
                # If only 1 position, set to TP1
                res = h.modify_position_bracket(pos_id, stop_loss=sl_level, take_profit=tp1_level)
                print(f"  -> Single Ticket ({pos_id}): SL={sl_level}, TP={tp1_level} -> Success: {res}")
        except Exception as e:
            print(f"Account {i+1} error: {e}")
        time.sleep(2.5)

    print("\n=== POST-CONFIGURATION AUDIT ===")
    for i, h in enumerate(tl.helpers):
        try:
            positions = h.get_open_positions()
            print(f"Account {i+1} ({h.email}):")
            for idx, p in enumerate(positions):
                print(f"   -> Ticket {idx+1} (ID: {p.get('id')}): Qty={p.get('qty')} | Price={p.get('price')} | PnL={p.get('pnl')}")
        except Exception as e:
            print(f"Account {i+1} audit error: {e}")

if __name__ == "__main__":
    main()

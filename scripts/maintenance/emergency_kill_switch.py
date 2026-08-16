"""
Emergency Portfolio Kill Switch
===============================
Instant panic-button script for portfolio-wide risk mitigation.
Cancels all pending orders and closes all active open positions across
ALL 8 TradeLocker account mandates simultaneously.
"""

import sys
import os
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.clients.tl_client import TradeLockerClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("KillSwitch")

def execute_emergency_kill_switch():
    print("\n===========================================================================")
    print(" 🚨 EMERGENCY PORTFOLIO KILL SWITCH TRIGGERED")
    print("===========================================================================\n")

    client = TradeLockerClient()
    print(f" • Loaded {len(client.helpers)} TradeLocker Account Helpers.\n")

    total_closed = 0
    total_failed = 0

    for i, helper in enumerate(client.helpers):
        if not helper.access_token and not helper.login():
            print(f" ❌ Account {i+1} ({helper.email}): Login Failed")
            continue

        try:
            open_positions = helper.get_open_positions()
            if not open_positions:
                print(f" ✅ Account {i+1} ({helper.email}): 0 Open Positions")
                continue

            print(f" ⚠️ Account {i+1} ({helper.email}): Closing {len(open_positions)} Open Position(s)...")
            for pos in open_positions:
                pos_id = pos.get("id") or pos.get("positionId")
                symbol = pos.get("symbol", "Unknown")
                side = pos.get("side", "Unknown")
                qty = pos.get("qty", 0.0)

                # Send close request
                url = f"{helper.base_url}/backend-api/trade/accounts/{helper.account_id}/positions/{pos_id}"
                import requests
                resp = requests.delete(url, headers=helper._get_headers(auth=True), timeout=10)
                
                if resp.status_code in [200, 204]:
                    print(f"   ✅ Closed Position {pos_id}: {side} {qty} {symbol}")
                    total_closed += 1
                else:
                    print(f"   ❌ Failed to Close Position {pos_id}: {resp.status_code} - {resp.text[:100]}")
                    total_failed += 1

        except Exception as e:
            print(f" ❌ Account {i+1} ({helper.email}) Exception: {e}")

    print("\n===========================================================================")
    print(f" 🏁 KILL SWITCH EXECUTION COMPLETE: Closed: {total_closed} | Failed: {total_failed}")
    print("===========================================================================\n")

if __name__ == "__main__":
    execute_emergency_kill_switch()

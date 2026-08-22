import os
import sys
import json
import time
import requests
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.clients.tl_client import TradeLockerClient

def take_partial_and_trail():
    logger.info("Initializing Partial Profit Taking & Trailing Stop Management...")
    tl = TradeLockerClient()
    
    close_accounts = [0, 1, 2, 3] # Close these 4 accounts to bank realized profits
    trail_accounts = [4, 5, 6, 7] # Move SL to $78,250 on these 4 accounts
    
    new_sl = 78250.0
    
    results = {
        "closed": [],
        "trailed": []
    }
    
    # 1. Close Accounts 0, 1, 2, 3
    for acc_idx in close_accounts:
        helper = tl.helpers[acc_idx]
        logger.info(f"--- Closing Account {acc_idx} ({helper.email}) ---")
        if not helper.access_token and not helper.login():
            logger.error(f"Login failed for Account {acc_idx}")
            continue
            
        try:
            positions = helper.get_open_positions()
            btc_pos = [p for p in positions if "BTC" in str(p.get("symbol", "")).upper() or str(p.get("tradableInstrumentId")) == "19965"]
            if not btc_pos:
                logger.info(f"No active BTC positions on Account {acc_idx}")
                continue
                
            for pos in btc_pos:
                pos_id = pos.get("id") or pos.get("positionId")
                qty = pos.get("qty")
                url = f"{helper.base_url}/backend-api/trade/accounts/{helper.account_id}/positions/{pos_id}"
                resp = requests.delete(url, headers=helper._get_headers(auth=True), timeout=10)
                if resp.status_code in [200, 204]:
                    logger.info(f"✅ Successfully CLOSED Account {acc_idx} position {pos_id} ({qty} BTC)")
                    results["closed"].append({
                        "account_index": acc_idx,
                        "email": helper.email,
                        "position_id": pos_id,
                        "qty": qty,
                        "status": "CLOSED"
                    })
                else:
                    logger.error(f"❌ Failed to close position {pos_id}: {resp.status_code} {resp.text}")
        except Exception as e:
            logger.error(f"Error processing close on Account {acc_idx}: {e}")
            
        time.sleep(1.5)

    # 2. Trail Stop Loss on Accounts 4, 5, 6, 7 to $78,250
    for acc_idx in trail_accounts:
        helper = tl.helpers[acc_idx]
        logger.info(f"--- Trailing Stop on Account {acc_idx} ({helper.email}) to SL={new_sl} ---")
        if not helper.access_token and not helper.login():
            logger.error(f"Login failed for Account {acc_idx}")
            continue
            
        try:
            positions = helper.get_open_positions()
            btc_pos = [p for p in positions if "BTC" in str(p.get("symbol", "")).upper() or str(p.get("tradableInstrumentId")) == "19965"]
            if not btc_pos:
                logger.info(f"No active BTC positions on Account {acc_idx}")
                continue
                
            for pos in btc_pos:
                pos_id = pos.get("id") or pos.get("positionId")
                qty = pos.get("qty")
                url = f"{helper.base_url}/backend-api/trade/accounts/{helper.account_id}/positions/{pos_id}"
                patch_payload = {
                    "stopLoss": float(new_sl),
                    "stopLossType": "absolute"
                }
                resp = requests.patch(url, json=patch_payload, headers=helper._get_headers(auth=True), timeout=10)
                if resp.status_code in [200, 204]:
                    logger.info(f"🛡️ Trailed SL on Account {acc_idx} position {pos_id} to ${new_sl}")
                    results["trailed"].append({
                        "account_index": acc_idx,
                        "email": helper.email,
                        "position_id": pos_id,
                        "qty": qty,
                        "new_sl": new_sl,
                        "status": "TRAILED"
                    })
                else:
                    logger.warning(f"⚠️ Patch SL returned: {resp.status_code} {resp.text}")
                    results["trailed"].append({
                        "account_index": acc_idx,
                        "position_id": pos_id,
                        "status": f"PATCH_RESP_{resp.status_code}"
                    })
        except Exception as e:
            logger.error(f"Error trailing SL on Account {acc_idx}: {e}")
            
        time.sleep(1.5)

    print("\n================ PARTIAL PROFIT & TRAIL REPORT ================")
    print(json.dumps(results, indent=2))
    print("=================================================================")

if __name__ == "__main__":
    take_partial_and_trail()

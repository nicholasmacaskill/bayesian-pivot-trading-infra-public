import os
import sys
import json
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.clients.tl_client import TradeLockerClient
from src.core.config import Config

def execute_all():
    logger.info("Initializing TradeLocker Multi-Account Execution for BTC/USD SHORT...")
    tl = TradeLockerClient()
    
    symbol = "BTC/USD"
    instrument_id = tl.resolve_instrument_id(symbol) # 19965
    side = "sell"
    sl_price = 79074.0
    tp_price = 77371.0
    
    results = []
    
    for i, helper in enumerate(tl.helpers):
        logger.info(f"--- Processing Account {i} ({helper.email}) ---")
        if not helper.access_token and not helper.login():
            logger.error(f"Failed to log in to Account {i}")
            results.append({"account_index": i, "email": helper.email, "status": "LOGIN_FAILED"})
            continue
            
        # Check balance to scale lot size
        balance = 25000.0
        try:
            url = f"{helper.base_url}/backend-api/auth/jwt/all-accounts"
            resp = helper.get_account_details()
            # If account details were retrieved
            open_pos = helper.get_open_positions()
            # Check if position already open
            existing_btc = [p for p in open_pos if str(p.get("tradableInstrumentId")) == str(instrument_id) or "BTC" in str(p.get("symbol", "")).upper()]
            if existing_btc:
                logger.warning(f"Account {i} already has active BTC position: {existing_btc}. Skipping.")
                results.append({"account_index": i, "email": helper.email, "status": "SKIPPED_ALREADY_OPEN", "details": existing_btc})
                continue
        except Exception as e:
            logger.warning(f"Could not verify existing positions on account {i}: {e}")

        # Sizing logic based on account index / balance
        # 50k -> 0.25, 25k -> 0.23, 10k -> 0.11
        if i in [1, 5]: # 50k
            lots = 0.25
        elif i in [0, 2, 6]: # 25k
            lots = 0.23
        else: # 10k (3, 4, 7)
            lots = 0.11
            
        logger.info(f"Submitting order for Account {i}: SELL {lots} BTC/USD | SL: {sl_price} | TP: {tp_price}")
        res = helper.place_order(
            instrument_id=instrument_id,
            side=side,
            qty=lots,
            stop_loss=sl_price,
            take_profit=tp_price,
            order_type="market"
        )
        
        if res:
            logger.info(f"✅ Account {i} Execution Success: {res}")
            results.append({"account_index": i, "email": helper.email, "status": "SUCCESS", "lots": lots, "order_resp": res})
        else:
            logger.error(f"❌ Account {i} Execution Failed")
            results.append({"account_index": i, "email": helper.email, "status": "FAILED"})
            
        time.sleep(2.5) # 2.5s pacing between account orders to prevent 429

    print("\n================ EXECUTION SUMMARY ================")
    print(json.dumps(results, indent=2))
    print("===================================================")

if __name__ == "__main__":
    execute_all()

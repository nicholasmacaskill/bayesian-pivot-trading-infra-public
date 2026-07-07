import os
import sys
import requests
from dotenv import load_dotenv

# Add root to sys.path
sys.path.append(os.getcwd())

from src.clients.tl_client import TradeLockerClient

def check_live_sl_tp():
    load_dotenv(".env.local")
    tl = TradeLockerClient()
    helper = tl.helpers[0]
    if not helper.access_token:
        helper.login()
    
    print("Fetching live positions and orders...")
    try:
        # 1. Fetch Positions
        url_pos = f"{helper.base_url}/backend-api/trade/accounts/{helper.account_id}/positions"
        resp_pos = requests.get(url_pos, headers=helper._get_headers(auth=True), timeout=10)
        positions = resp_pos.json().get('d', {}).get('positions', [])
        
        # 2. Fetch Orders (to find SL/TP prices)
        url_orders = f"{helper.base_url}/backend-api/trade/accounts/{helper.account_id}/orders"
        resp_orders = requests.get(url_orders, headers=helper._get_headers(auth=True), timeout=10)
        orders = resp_orders.json().get('d', {}).get('orders', [])
        
        print("-" * 50)
        for p in positions:
            if isinstance(p, list):
                pos_id = str(p[0])
                qty = p[4]
                entry = p[5]
                pnl = p[9]
                sl_id = str(p[6])
                tp_id = str(p[7])
                
                print(f"POSITION: {pos_id}")
                print(f"Entry: {entry} | Qty: {qty} | PnL: ${pnl}")
                
                # Find matching orders for SL/TP
                for o in orders:
                    if isinstance(o, list):
                        o_id = str(o[0])
                        if o_id == sl_id:
                            print(f"STOP LOSS (Order {o_id}): {o[9] or o[8]}") # Try common price indices
                        if o_id == tp_id:
                            print(f"TAKE PROFIT (Order {o_id}): {o[9] or o[8]}")
            print("-" * 50)
            
        # Also print raw orders for debugging
        print("\nRAW ORDERS (Top 5):")
        for o in orders[:5]:
            print(o)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_live_sl_tp()

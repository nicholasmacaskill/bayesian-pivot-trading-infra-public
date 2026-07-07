import os
import sys
import requests
import json
from datetime import datetime

# Add src to path
sys.path.append(os.getcwd())

from src.clients.tl_client import TradeLockerClient
from dotenv import load_dotenv

def brute_force_order_status():
    print("🔌 Brute-forcing TradeLocker Order Statuses...")
    load_dotenv(".env.local")
    tl = TradeLockerClient()
    h = tl.helpers[0]
    h.login()
    
    url = f"{h.base_url}/backend-api/trade/accounts/{h.account_id}/orders"
    
    # Common status codes in some TL versions: 
    # 2=Filled, 4=Cancelled, 6=New
    codes = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    
    for code in codes:
        print(f"   Testing Status Code {code}...")
        try:
            resp = requests.get(url, headers=h._get_headers(auth=True), params={'status': code, 'limit': 10}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                orders = data.get('d', {}).get('orders', [])
                if orders:
                    print(f"      ✅ Found {len(orders)} orders with status {code}!")
                    for o in orders[:3]:
                        print(f"         - {o}")
            else:
                print(f"      - Error {resp.status_code}")
        except Exception as e:
            print(f"      - Exception: {e}")

if __name__ == "__main__":
    brute_force_order_status()

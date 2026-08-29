import sys
import os
sys.path.append(os.getcwd())

import requests
from src.clients.tl_client import TradeLockerClient

def main():
    tl = TradeLockerClient()
    print("=== RAW TRADELOCKER ACCOUNT DISCOVERY & ORDERS (ZERO INTERPRETATION) ===")

    for i, h in enumerate(tl.helpers):
        try:
            h.login()
            url = f"{h.base_url}/backend-api/auth/jwt/all-accounts"
            resp = requests.get(url, headers=h._get_headers(auth=True), timeout=10)
            acc_data = resp.json().get('accounts', [{}])[0]
            
            # Fetch raw orders history
            url_orders = f"{h.base_url}/backend-api/trade/accounts/{acc_data.get('id')}/ordersHistory"
            resp_orders = requests.get(url_orders, headers=h._get_headers(auth=True), timeout=10)
            raw_orders = resp_orders.json().get('d', {}).get('ordersHistory', [])
            
            print(f"\n==========================================")
            print(f"ACCOUNT {i+1}: {h.email}")
            print(f"Account ID: {acc_data.get('id')} | Name: {acc_data.get('name')}")
            print(f"Current Raw Balance: ${acc_data.get('accountBalance')} {acc_data.get('currency')}")
            print(f"Total Orders in History: {len(raw_orders)}")
            print("Last 4 Orders:")
            for o in raw_orders[:4]:
                print(f"   Row: {o}")
        except Exception as e:
            print(f"Account {i+1} error: {e}")

if __name__ == "__main__":
    main()

import os
import sys
import requests
import json
from datetime import datetime

# Add src to path
sys.path.append(os.getcwd())

from src.clients.tl_client import TradeLockerClient
from dotenv import load_dotenv

def discover_history():
    print("🕵️‍♂️ Deep History Discovery...")
    load_dotenv(".env.local")
    tl = TradeLockerClient()
    h = tl.helpers[0]
    h.login()
    
    # 1. Probing order history formats
    history_urls = [
        f"{h.base_url}/backend-api/trade/accounts/{h.account_id}/orders-history",
        f"{h.base_url}/backend-api/trade/accounts/{h.account_id}/orders?status=filled",
        f"{h.base_url}/backend-api/trade/accounts/{h.account_id}/positions?status=closed",
        f"{h.base_url}/backend-api/trade/accounts/{h.account_id}/history",
        f"{h.base_url}/backend-api/trade/history"
    ]
    
    for url in history_urls:
        print(f"\n   Testing: {url}")
        try:
            resp = requests.get(url, headers=h._get_headers(auth=True), params={'limit': 20}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get('d', {}).get('orders') or data.get('d', {}).get('positions') or data.get('d', {}).get('history') or data
                if items:
                    print(f"      ✅ FOUND {len(items)} items!")
                    print(json.dumps(items, indent=2)[:2000])
                    # If we found items, we can stop or continue
                else:
                    print("      Items list empty.")
            else:
                print(f"      Error {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            print(f"      Exception: {e}")

if __name__ == "__main__":
    discover_history()

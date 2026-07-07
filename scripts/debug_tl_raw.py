import os
import sys
import requests
import json
from datetime import datetime

# Add src to path
sys.path.append(os.getcwd())

from src.clients.tl_client import TradeLockerClient
from dotenv import load_dotenv

def debug_tl_raw():
    print("🔌 RAW TradeLocker Debugger...")
    load_dotenv(".env.local")
    tl = TradeLockerClient()
    
    for i, helper in enumerate(tl.helpers):
        print(f"\n--- Account {i+1} ({helper.email}) ---")
        if not helper.access_token:
            if not helper.login(): continue
            
        # 1. Try different history endpoints
        endpoints = [
            f"{helper.base_url}/backend-api/trade/accounts/{helper.account_id}/history",
            f"{helper.base_url}/backend-api/trade/accounts/{helper.account_id}/orders",
            f"{helper.base_url}/backend-api/trade/accounts/{helper.account_id}/trades",
            f"{helper.base_url}/backend-api/trade/history"
        ]
        
        for url in endpoints:
            print(f"\n   Testing: {url}")
            try:
                resp = requests.get(url, headers=helper._get_headers(auth=True), params={'limit': 10}, timeout=10)
                print(f"   Status: {resp.status_code}")
                if resp.status_code == 200:
                    data = resp.json()
                    print(f"   Response (Raw): {json.dumps(data, indent=2)[:2000]}")
                else:
                    print(f"   Error: {resp.text[:200]}")
            except Exception as e:
                print(f"   Exception: {e}")

if __name__ == "__main__":
    debug_tl_raw()

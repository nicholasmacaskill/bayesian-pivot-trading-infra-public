import os
import sys
import requests
import json
from datetime import datetime

# Add src to path
sys.path.append(os.getcwd())

from src.clients.tl_client import TradeLockerClient
from dotenv import load_dotenv

def probe_all_history():
    print("🔌 Comprehensive TradeLocker History Probe...")
    load_dotenv(".env.local")
    tl = TradeLockerClient()
    
    for i, helper in enumerate(tl.helpers):
        print(f"\n--- Account {i+1} ({helper.email}) ---")
        if not helper.access_token:
            if not helper.login(): continue
            
        endpoints = [
            f"{helper.base_url}/backend-api/trade/accounts/{helper.account_id}/positions/history",
            f"{helper.base_url}/backend-api/trade/accounts/{helper.account_id}/orders/history",
            f"{helper.base_url}/backend-api/trade/accounts/{helper.account_id}/trades/history",
            f"{helper.base_url}/backend-api/trade/positions/history",
            f"{helper.base_url}/backend-api/trade/orders/history"
        ]
        
        for url in endpoints:
            print(f"   Checking: {url}")
            try:
                resp = requests.get(url, headers=helper._get_headers(auth=True), params={'limit': 10}, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    # Check for data in 'd' or root
                    items = data.get('d', {}).get('positions') or data.get('d', {}).get('orders') or data.get('d', {}).get('trades') or data
                    if items and len(items) > 0:
                        print(f"   ✅ SUCCESS: Found data at {url}")
                        print(f"   Sample: {json.dumps(items, indent=2)[:500]}")
                        return # Exit after first success for brevity
                else:
                    pass # Silently fail for other endpoints
            except Exception:
                pass

if __name__ == "__main__":
    probe_all_history()

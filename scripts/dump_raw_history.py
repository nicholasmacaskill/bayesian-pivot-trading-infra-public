import os
import sys
import json
from datetime import datetime

# Add src to path
sys.path.append(os.getcwd())

from src.clients.tl_client import TradeLockerClient
from dotenv import load_dotenv

def dump_all_history():
    print("🕵️‍♂️ Dumping absolute last history entries from TradeLocker...")
    load_dotenv(".env")
    load_dotenv(".env.local")
    tl = TradeLockerClient()
    
    for i, helper in enumerate(tl.helpers):
        print(f"\n--- Account {i+1} ({helper.email}) ---")
        if not helper.access_token:
            if not helper.login(): 
                print("   Failed login")
                continue
            
        print(f"   Using Account ID: {helper.account_id}")
        
        # Try a few different endpoints if history is empty
        endpoints = [
            f"{helper.base_url}/backend-api/trade/accounts/{helper.account_id}/history",
            f"{helper.base_url}/backend-api/trade/history"
        ]
        
        found = False
        for url in endpoints:
            print(f"   Checking: {url}")
            try:
                resp = helper.session.get(url, headers=helper._get_headers(auth=True), params={'limit': 50}, timeout=10) if hasattr(helper, 'session') else None
                # Since helper doesn't have a 'session' but uses requests directly in tl_client:
                import requests
                resp = requests.get(url, headers=helper._get_headers(auth=True), params={'limit': 50}, timeout=10)
                
                if resp.status_code == 200:
                    data = resp.json()
                    positions = data.get('d', {}).get('positions', [])
                    if not positions and isinstance(data, list): positions = data
                    if positions:
                        print(f"   ✅ Found {len(positions)} records at this endpoint.")
                        for p in positions[:5]:
                            p_id = p.get('id')
                            symbol = helper.resolve_symbol(p.get('instrumentId'))
                            side = p.get('side')
                            profit = p.get('profit')
                            close_date = p.get('closeDate') or p.get('filledAt')
                            print(f"      - ID: {p_id} | {symbol} {side} | PnL: {profit} | Date: {close_date}")
                        found = True
                        break
                else:
                    print(f"      - {url} returned {resp.status_code}")
            except Exception as e:
                print(f"      - Error at {url}: {e}")
        
        if not found:
            print("   No history records found for this account in recent 50 entries.")

if __name__ == "__main__":
    dump_all_history()

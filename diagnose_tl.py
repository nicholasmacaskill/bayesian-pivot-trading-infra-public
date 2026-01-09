import os
import logging
from tradelocker_client import TradeLockerClient

# Setup logging to see what's happening
logging.basicConfig(level=logging.INFO)

def diagnose_sync():
    print("🧪 TradeLocker Multi-Account Diagnostic...")
    
    # Check Env Vars Presence
    vars_a = ["TRADELOCKER_EMAIL_A", "TRADELOCKER_PASSWORD_A", "TRADELOCKER_SERVER_A"]
    vars_b = ["TRADELOCKER_EMAIL_B", "TRADELOCKER_PASSWORD_B", "TRADELOCKER_SERVER_B"]
    
    print("\n[Account A Config]")
    for v in vars_a:
        exists = os.environ.get(v) is not None or os.environ.get(v.replace("_A", "")) is not None
        print(f"  {v}: {'SET' if exists else 'MISSING'}")
        
    print("\n[Account B Config]")
    for v in vars_b:
        exists = os.environ.get(v) is not None
        print(f"  {v}: {'SET' if exists else 'MISSING'}")

    tl = TradeLockerClient()
    print(f"\n[Client Init] Helpers Loaded: {len(tl.helpers)}")
    
    for i, helper in enumerate(tl.helpers):
        label = "A" if i == 0 else "B"
        print(f"\n🔍 Testing Account {label} ({helper.email})...")
        if helper.login():
            print(f"  ✅ Login SUCCESS")
            print(f"  ✅ Account ID: {helper.account_id}")
            # Try to get equity specifically for this helper
            # Need to access helper._get_headers and url
            import requests
            url = f"{helper.base_url}/backend-api/auth/jwt/all-accounts"
            resp = requests.get(url, headers=helper._get_headers(auth=True), timeout=10)
            if resp.status_code == 200:
                accounts = resp.json().get('accounts', [])
                for acc in accounts:
                    p_equity = acc.get('projectedEquity', 'N/A')
                    balance = acc.get('accountBalance', 'N/A')
                    print(f"    - Sub-Account {acc['id']}: Projected Equity: ${p_equity} | Balance: ${balance}")
        else:
            print(f"  ❌ Login FAILED")

if __name__ == "__main__":
    diagnose_sync()

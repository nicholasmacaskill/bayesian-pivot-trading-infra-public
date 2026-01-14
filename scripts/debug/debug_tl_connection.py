
import os
import requests
import logging

try:
    from dotenv import load_dotenv
    load_dotenv('.env.local')
    print("✅ Loaded .env.local file")
except ImportError:
    print("⚠️ dotenv module not found. Reliance on system env vars.")

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def debug_connection():
    print("\n--- DEBUG TL CONNECTION ---")
    
    # Define Accounts
    accounts = [
        {
            "name": "Account A",
            "email": os.environ.get("TRADELOCKER_EMAIL_A") or os.environ.get("TRADELOCKER_EMAIL"),
            "password": os.environ.get("TRADELOCKER_PASSWORD_A") or os.environ.get("TRADELOCKER_PASSWORD"),
            "server": os.environ.get("TRADELOCKER_SERVER_A") or os.environ.get("TRADELOCKER_SERVER"),
            "base": os.environ.get("TRADELOCKER_BASE_URL_A") or os.environ.get("TRADELOCKER_BASE_URL")
        },
        {
            "name": "Account B",
            "email": os.environ.get("TRADELOCKER_EMAIL_B"),
            "password": os.environ.get("TRADELOCKER_PASSWORD_B"),
            "server": os.environ.get("TRADELOCKER_SERVER_B"),
            "base": os.environ.get("TRADELOCKER_BASE_URL_B")
        }
    ]

    for acc in accounts:
        name = acc['name']
        print(f"\n--- DEBUG {name} ---")
        
        email = acc['email']
        password = acc['password']
        server = acc['server']
        base_url = acc['base']
        
        print(f"EMAIL: {'*' * 5 if email else 'MISSING'}")
        print(f"PASSWORD: {'*' * 5 if password else 'MISSING'}")
        print(f"SERVER: {server}")
        print(f"BASE_URL: {base_url}")
        
        if not all([email, password, server, base_url]):
            print(f"❌ Skipping {name}: Missing Environment Variables!")
            continue

        # Attempt Login
        try:
            url = f"{base_url.rstrip('/')}/backend-api/auth/jwt/token"
            payload = {
                "email": email.strip(),
                "password": password,
                "server": server
            }
            
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Content-Type": "application/json"
            }
            
            print(f"Attempting Login to: {url}")
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            
            if resp.status_code in [200, 201]:
                token = resp.json().get('accessToken')
                print(f"✅ {name} Login Successful.")
                
                auth_headers = headers.copy()
                auth_headers["Authorization"] = f"Bearer {token}"
                
                # Get All Accounts
                acc_url = f"{base_url.rstrip('/')}/backend-api/auth/jwt/all-accounts"
                acc_resp = requests.get(acc_url, headers=auth_headers)
                
                if acc_resp.status_code == 200:
                    data = acc_resp.json()
                    accounts_data = data.get('accounts', [])
                    print(f"✅ {name} Found {len(accounts_data)} internal accounts.")
                    for a in accounts_data:
                        equity = float(a.get('projectedEquity') or a.get('accountBalance', 0.0))
                        print(f"   - ID: {a.get('id')} | Equity: ${equity:,.2f}")
                else:
                    print(f"   ⚠️ Found token but failed to fetch account details: {acc_resp.status_code}")
                
            else:
                print(f"❌ {name} Login Failed: {resp.status_code}")
                # print(resp.text) # Uncomment if needed

        except Exception as e:
            print(f"❌ {name} Exception: {e}")

if __name__ == "__main__":
    debug_connection()

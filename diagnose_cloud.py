import modal
import os
import requests

# Connect to the SAME secrets as the main app
stub = modal.App("smc-cloud-diagnostic")

image = modal.Image.debian_slim().pip_install("requests", "python-dotenv")

@stub.function(
    image=image,
    secrets=[modal.Secret.from_name("smc-secrets")]
)
def diagnose():
    print("🔎 --- CLOUD DIAGNOSTIC START ---")
    
    # 1. Check Env Vars
    vars_to_check = [
        "TRADELOCKER_EMAIL", "TRADELOCKER_EMAIL_A", "TRADELOCKER_EMAIL_B",
        "TRADELOCKER_PASSWORD", "TRADELOCKER_PASSWORD_A", "TRADELOCKER_PASSWORD_B",
        "TRADELOCKER_SERVER", "TRADELOCKER_SERVER_B",
        "TRADELOCKER_BASE_URL", "TRADELOCKER_BASE_URL_B"
    ]
    
    print("📝 Environment Variables:")
    for v in vars_to_check:
        val = os.environ.get(v)
        status = "✅ Set" if val else "❌ MISSING"
        # Mask password
        if "PASSWORD" in v and val:
            val = "*****"
        print(f"   {v}: {val} ({status})")

    # 2. Logic Check (Mimic tl_client.py)
    server_a = os.environ.get("TRADELOCKER_SERVER_A") or os.environ.get("TRADELOCKER_SERVER") or "UPCOMS"
    base_url_a = os.environ.get("TRADELOCKER_BASE_URL_A") or os.environ.get("TRADELOCKER_BASE_URL") or "https://demo.tradelocker.com"
    
    accounts = []
    
    # helper A
    email_a = os.environ.get("TRADELOCKER_EMAIL_A") or os.environ.get("TRADELOCKER_EMAIL")
    pass_a = os.environ.get("TRADELOCKER_PASSWORD_A") or os.environ.get("TRADELOCKER_PASSWORD")
    if email_a and pass_a:
        accounts.append({"name": "Account A", "email": email_a, "pw": pass_a, "server": server_a, "base": base_url_a})
        
    # helper B
    email_b = os.environ.get("TRADELOCKER_EMAIL_B")
    pass_b = os.environ.get("TRADELOCKER_PASSWORD_B")
    server_b = os.environ.get("TRADELOCKER_SERVER_B") or server_a
    base_url_b = os.environ.get("TRADELOCKER_BASE_URL_B") or base_url_a
    
    if email_b and pass_b:
        accounts.append({"name": "Account B", "email": email_b, "pw": pass_b, "server": server_b, "base": base_url_b})
        
    print(f"\n💡 Detected {len(accounts)} accounts configured in logic.")
    
    # 3. Connectivity Check
    for acc in accounts:
        print(f"\n🔌 Testing {acc['name']}...")
        try:
            url = f"{acc['base'].rstrip('/')}/backend-api/auth/jwt/token"
            payload = {
                "email": acc['email'],
                "password": acc['pw'],
                "server": acc['server']
            }
            # Add headers to match tl_client
            headers = {"Content-Type": "application/json"}
            
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            print(f"   Login Status: {resp.status_code}")
            
            if resp.status_code in [200, 201]:
                token = resp.json().get('accessToken')
                print("   ✅ Login OK")
                
                # Fetch equity
                auth_headers = {"Authorization": f"Bearer {token}"}
                acc_url = f"{acc['base'].rstrip('/')}/backend-api/auth/jwt/all-accounts"
                acc_resp = requests.get(acc_url, headers=auth_headers)
                
                if acc_resp.status_code == 200:
                    data = acc_resp.json()
                    equity = 0.0
                    for a in data.get('accounts', []):
                         equity += float(a.get('projectedEquity') or a.get('accountBalance', 0.0))
                         print(f"      - ID: {a['id']} Equity: ${equity:,.2f}")
                else:
                    print(f"   ❌ Failed to fetch accounts: {acc_resp.status_code}")
            else:
                print(f"   ❌ Login Failed: {resp.text}")
                
        except Exception as e:
            print(f"   ❌ Exception: {e}")

    print("\n🔎 --- CLOUD DIAGNOSTIC END ---")

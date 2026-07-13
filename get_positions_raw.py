import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
try:
    from src.clients.tl_client import TradeLockerClient
    import requests
    import json
    
    tl = TradeLockerClient()
    tl.login()
    headers = tl._get_headers(auth=True)
    acc = tl.get_account_details()
    if not acc:
        print("No acc")
    else:
        acc_id = acc.get('id')
        res = requests.get(f"{tl.base_url}/trade/accounts/{acc_id}/positions", headers=headers)
        print(json.dumps(res.json(), indent=2))
except Exception as e:
    print(f"Error: {e}")

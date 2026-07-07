from src.clients.tl_client import TradeLockerClient
import requests
tl = TradeLockerClient()
h = tl.helpers[0]
h.login()
res = requests.get(f"{h.base_url}/backend-api/instrument/instruments", headers=h._get_headers(auth=True))
print(res.json())

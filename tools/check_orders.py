import sys
import os
from dotenv import load_dotenv

load_dotenv(".env.local")
load_dotenv()

from src.clients.tl_client import TradeLockerHelper
import requests

email = os.environ.get("TRADELOCKER_EMAIL_A") or os.environ.get("TRADELOCKER_EMAIL")
password = os.environ.get("TRADELOCKER_PASSWORD_A") or os.environ.get("TRADELOCKER_PASSWORD")
server = os.environ.get("TRADELOCKER_SERVER_A") or os.environ.get("TRADELOCKER_SERVER")
base_url = os.environ.get("TRADELOCKER_BASE_URL_A") or os.environ.get("TRADELOCKER_BASE_URL", "https://demo.tradelocker.com")

helper = TradeLockerHelper(email, password, server, base_url)
if helper.login():
    url_orders = f"{helper.base_url}/backend-api/trade/accounts/{helper.account_id}/orders"
    resp = requests.get(url_orders, headers=helper._get_headers(auth=True))
    data = resp.json()
    orders = data.get("d", {}).get("orders", [])
    if not orders and isinstance(data, list): orders = data
    
    for o in orders:
        if isinstance(o, list):
            print(f"ORDER LIST: {o}")
        else:
            print(f"ORDER DICT: {o}")

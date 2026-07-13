import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
try:
    from src.clients.tl_client import TradeLockerClient
    import json
    
    tl = TradeLockerClient()
    # the client has a get_account_details or get_recent_history
    # Wait, the position data might be in the raw tl_client.get_open_positions() output
    # But tl_client returns a cleaned list of dicts. Let's look at the client source.
    print(json.dumps(tl.get_open_positions(), indent=2))
except Exception as e:
    print(f"Error: {e}")

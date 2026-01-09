
import os
from dotenv import load_dotenv
import logging
from tradelocker_client import TradeLockerClient

# Configure logging to show everything
logging.basicConfig(level=logging.INFO)

# Load env vars
load_dotenv(".env.local")

print("--- Debugging TradeLocker Connection ---")

client = TradeLockerClient()
print(f"Loaded {len(client.helpers)} account helpers.")

# Check Total Equity (Should be $49k, not $98k)
print("\n--- Verifying Deduplication ---")
total_equity = client.get_total_equity()
print(f"Total Combined Equity: ${total_equity:,.2f}")

print("\n--- End Debug ---")

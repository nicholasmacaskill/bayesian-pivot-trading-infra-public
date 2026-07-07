import os
import sys
import json
import pandas as pd
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.getcwd())

from src.clients.tl_client import TradeLockerClient
from dotenv import load_dotenv

def extract_manual_trades(days_lookback=30):
    """
    Harvests manual trade history from all TradeLocker accounts.
    Saves to data/manual_trades.json for pattern analysis.
    """
    print(f"🕵️‍♂️ Starting Alpha Harvest (Lookback: {days_lookback} days)...")
    load_dotenv(".env")
    load_dotenv(".env.local")
    
    tl = TradeLockerClient()
    all_manual_trades = []
    
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    for i, helper in enumerate(tl.helpers):
        print(f"\n--- Account {i+1} ({helper.email}) ---")
        if not helper.access_token:
            if not helper.login():
                print("   ❌ Failed login")
                continue
        
        # Try multiple endpoints as TradeLocker versions vary
        endpoints = [
            f"{helper.base_url}/backend-api/trade/accounts/{helper.account_id}/history",
            f"{helper.base_url}/backend-api/trade/history"
        ]
        
        found_at_endpoint = False
        for url in endpoints:
            if found_at_endpoint: break
            print(f"   🔎 Checking: {url}")
            try:
                import requests
                # Fetch with a high limit to get as much history as possible
                resp = requests.get(url, headers=helper._get_headers(auth=True), params={'limit': 200}, timeout=15)
                
                if resp.status_code == 200:
                    data = resp.json()
                    positions = data.get('d', {}).get('positions', [])
                    if not positions and isinstance(data, list): positions = data
                    
                    if not positions:
                        print(f"      - Endpoint succeeded but returned 0 trades.")
                        continue

                    print(f"   ✅ Success! Found {len(positions)} closed records.")
                    found_at_endpoint = True
                    
                    for p in positions:
                        # Capture core fields for Delta Analysis
                        close_date = p.get('closeDate') or p.get('filledAt')
                        open_date = p.get('openDate') or p.get('created')
                        
                        # Basic noise filter: ignore tiny trades or errors
                        if not close_date or not open_date: continue
                        
                        trade_record = {
                            "id": p.get('id'),
                            "symbol": helper.resolve_symbol(p.get('instrumentId')),
                            "side": p.get('side').upper() if p.get('side') else 'UNKNOWN',
                            "qty": float(p.get('qty', 0.0)),
                            "entry_price": float(p.get('openPrice', 0.0)),
                            "exit_price": float(p.get('closePrice', 0.0) or p.get('avgClosePrice', 0.0)),
                            "pnl": float(p.get('profit', 0.0)),
                            "entry_time": open_date,
                            "exit_time": close_date,
                            "close_reason": p.get('closeReason', 'Unknown')
                        }
                        
                        # Convert to datetime for sorting and filtering
                        try:
                            dt_close = pd.to_datetime(close_date)
                            if dt_close > (datetime.now() - timedelta(days=days_lookback)):
                                 all_manual_trades.append(trade_record)
                        except:
                            all_manual_trades.append(trade_record)
                else:
                    print(f"      ❌ Endpoint failed: {resp.status_code}")
            except Exception as e:
                print(f"      🚨 Error harvesting: {e}")

    # Save to file
    if all_manual_trades:
        output_path = "data/manual_trades.json"
        with open(output_path, "w") as f:
            json.dump(all_manual_trades, f, indent=4)
        print(f"\n🎉 ALPHA HARVEST COMPLETE: {len(all_manual_trades)} trades saved to {output_path}")
    else:
        print("\n⚠️ No trades harvested. Check connection or history availability.")

if __name__ == "__main__":
    extract_manual_trades(days_lookback=60) # Go deep

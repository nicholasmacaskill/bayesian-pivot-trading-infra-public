import os
import sys
import pandas as pd
from datetime import datetime

# Add root directory to path
sys.path.append(os.getcwd())

if os.path.exists(".env.local"):
    with open(".env.local", "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

from src.core.supabase_client import SupabaseBridge
from src.engines.smc_scanner import SMCScanner

def debug_scan():
    sb = SupabaseBridge()
    scanner = SMCScanner()
    
    # Fetch scan 22517
    res = sb.client.table("scans").select("*").eq("id", 22517).execute()
    if not res.data:
        print("Scan not found.")
        return
        
    scan = res.data[0]
    print("=== SCAN DETAILS ===")
    for k, v in scan.items():
        print(f"{k}: {v}")
        
    ts_str = scan['timestamp'].replace('Z', '').split('+')[0]
    ts = datetime.fromisoformat(ts_str)
    since_ms = int(ts.timestamp() * 1000)
    
    print(f"\nFetching candles since: {ts} (ms: {since_ms})")
    ohlcv = scanner.exchange.fetch_ohlcv(
        scan['symbol'].replace('USD', 'USDT'),
        '5m',
        since=since_ms,
        limit=10
    )
    
    print(f"\nRetrieved {len(ohlcv)} candles:")
    for candle in ohlcv:
        candle_time = datetime.utcfromtimestamp(candle[0]/1000.0)
        print(f"Time: {candle_time}, Open: {candle[1]}, High: {candle[2]}, Low: {candle[3]}, Close: {candle[4]}")

if __name__ == '__main__':
    debug_scan()

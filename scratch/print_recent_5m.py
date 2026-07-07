import sys
import os
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner

def print_recent_5m():
    scanner = SMCScanner()
    symbol = "BTC/USD"
    df = scanner.fetch_data(symbol, "5m", limit=10)
    if df is None:
        print("Failed to fetch.")
        return
        
    print(df[['timestamp', 'open', 'high', 'low', 'close', 'volume']])

if __name__ == "__main__":
    print_recent_5m()

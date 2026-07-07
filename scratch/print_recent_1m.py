import sys
import os
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner

def print_recent_1m():
    scanner = SMCScanner()
    symbol = "BTC/USD"
    df = scanner.fetch_data(symbol, "1m", limit=20)
    if df is None:
        print("Failed to fetch.")
        return
        
    print(df[['timestamp', 'open', 'high', 'low', 'close', 'volume']])

if __name__ == "__main__":
    print_recent_1m()

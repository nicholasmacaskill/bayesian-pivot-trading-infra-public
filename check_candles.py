from src.engines.smc_scanner import SMCScanner
import pandas as pd

def check_candles():
    scanner = SMCScanner()
    symbol = "BTC/USD"
    
    print(f"Fetching last 5 candles for {symbol}...")
    df = scanner.fetch_data(symbol, "5m", limit=5)
    
    if df is None or df.empty:
        print("Failed to fetch data.")
        return

    print(df[['timestamp', 'open', 'high', 'low', 'close']].tail(5))

if __name__ == "__main__":
    check_candles()

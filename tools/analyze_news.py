from src.engines.smc_scanner import SMCScanner
import pandas as pd
from datetime import datetime

def check_news_reaction():
    scanner = SMCScanner()
    symbol = "BTC/USD"
    
    print(f"Fetching last 100 5m candles for {symbol}...")
    df = scanner.fetch_data(symbol, "5m", limit=100)
    
    if df is None or df.empty:
        print("Failed to fetch data.")
        return

    # Convert timestamp to human readable UTC
    df['time_utc'] = pd.to_datetime(df['timestamp'], unit='ms').dt.strftime('%H:%M')
    
    print("\nRecent Price Action (5m UTC):")
    print(df[['time_utc', 'open', 'high', 'low', 'close']].tail(30))

if __name__ == "__main__":
    check_news_reaction()

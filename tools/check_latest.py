from src.engines.smc_scanner import SMCScanner
import pandas as pd
from datetime import datetime

def check_latest():
    scanner = SMCScanner()
    symbol = "BTC/USD"
    
    ticker = scanner.exchange.fetch_ticker(symbol)
    print(f"Latest Ticker Price: ${ticker['last']:,.2f}")
    
    # Check if there are any 1m candles for the last 15 mins
    print(f"\nFetching last 15 1m candles...")
    df_1m = scanner.exchange.fetch_ohlcv(symbol, timeframe='1m', limit=15)
    df_1m = pd.DataFrame(df_1m, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df_1m['time_utc'] = pd.to_datetime(df_1m['timestamp'], unit='ms').dt.strftime('%H:%M')
    print(df_1m[['time_utc', 'open', 'high', 'low', 'close']].tail(15))

if __name__ == "__main__":
    check_latest()

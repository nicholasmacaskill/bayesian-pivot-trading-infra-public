import ccxt
import pandas as pd
from datetime import datetime, timezone, timedelta

def test_depth():
    exchange = ccxt.binance({
        'options': {'defaultType': 'future'}
    })
    
    # 3 months ago
    start_time = datetime.now(timezone.utc) - timedelta(days=90)
    since = int(start_time.timestamp() * 1000)
    
    print(f"Requesting candles since: {start_time}")
    try:
        candles = exchange.fetch_ohlcv('BTC/USDT', '5m', since, 1000)
        print(f"Returned {len(candles)} candles.")
        if candles:
            first = datetime.utcfromtimestamp(candles[0][0]/1000.0)
            last = datetime.utcfromtimestamp(candles[-1][0]/1000.0)
            print(f"First candle: {first}")
            print(f"Last candle: {last}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    test_depth()

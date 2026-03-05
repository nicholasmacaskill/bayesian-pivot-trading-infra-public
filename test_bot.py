import ccxt
import certifi
print("Certifi path:", certifi.where())
def check():
    exchange = ccxt.coinbase({'enableRateLimit': True})
    print("Exchange:", exchange.id)
    try:
        ohlcv = exchange.fetch_ohlcv('BTC/USD', '1m', limit=5)
        print("Success!", len(ohlcv))
    except Exception as e:
        print("Error:", e)

check()

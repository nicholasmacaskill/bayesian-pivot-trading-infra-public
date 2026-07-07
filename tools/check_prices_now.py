import ccxt
from dotenv import load_dotenv
import os

load_dotenv(".env.local")
load_dotenv()

def get_prices():
    exchange = ccxt.binance()
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
    for s in symbols:
        ticker = exchange.fetch_ticker(s)
        print(f"{s}: {ticker['last']}")

if __name__ == '__main__':
    get_prices()

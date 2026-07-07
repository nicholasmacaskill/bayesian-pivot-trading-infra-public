import sys
import os

sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner

scanner = SMCScanner()
symbol = "BTC/USD"

df_1d = scanner.fetch_data(symbol, '1d', limit=100)
df_4h = scanner.fetch_data(symbol, '4h', limit=100)
df_1h = scanner.fetch_data(symbol, '1h', limit=100)

def get_tf_bias(df):
    ema20 = df['close'].ewm(span=20).mean().iloc[-1]
    ema50 = df['close'].ewm(span=50).mean().iloc[-1]
    return 1 if ema20 > ema50 else -1

b_1d = get_tf_bias(df_1d)
b_4h = get_tf_bias(df_4h)
b_1h = get_tf_bias(df_1h)

print(f"Daily Bias (1D): {b_1d} ({'BULLISH' if b_1d == 1 else 'BEARISH'})")
print(f"4H Bias:        {b_4h} ({'BULLISH' if b_4h == 1 else 'BEARISH'})")
print(f"1H Bias:        {b_1h} ({'BULLISH' if b_1h == 1 else 'BEARISH'})")


import sys
import os
import pandas as pd

# Add the project root to the python path
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner

def check_conditions():
    scanner = SMCScanner()
    symbol = "BTC/USD"
    
    # 15m for entry precision
    df_15m = scanner.fetch_data(symbol, '15m', limit=100)
    df_15m['rsi'] = scanner.calculate_rsi(df_15m)
    df_15m['ema_20'] = df_15m['close'].ewm(span=20).mean()
    
    last = df_15m.iloc[-1]
    
    print(f"--- 15m Snapshot ---")
    print(f"Price: ${last['close']:,.2f}")
    print(f"EMA 20: ${last['ema_20']:,.2f}")
    print(f"RSI: {last['rsi']:.2f}")
    
    dist_from_ema = ((last['ema_20'] - last['close']) / last['close']) * 100
    print(f"Extension from EMA: {dist_from_ema:.2f}%")
    
    if last['rsi'] < 30:
        print("\n⚠️ OVERSOLD: Price is deep in the trenches. High risk of a 'Snapback' to retest the EMA or $64k.")
    
    if dist_from_ema > 1.0:
        print("⚠️ EXTENDED: Price is far from its mean. Avoid selling into 'The Hole'.")

if __name__ == "__main__":
    check_conditions()

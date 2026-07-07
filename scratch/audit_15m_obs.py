import os
import sys
import pandas as pd
from dotenv import load_dotenv

# Add the project root to sys.path
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner

def main():
    load_dotenv('.env.local')
    scanner = SMCScanner()
    symbol = "BTC/USD"
    tf = "15m"
    
    print(f"--- 15m Bullish OB Audit for {symbol} ---")
    df = scanner.fetch_data(symbol, tf, limit=200)
    if df is None:
        print("Failed to fetch data.")
        return
    
    obs = scanner.detect_obs(df)
    bullish_obs = [ob for ob in obs if ob['type'] == 'BULLISH']
    
    current_price = df.iloc[-1]['close']
    print(f"Current Price: {current_price}")
    
    for ob in bullish_obs:
        status = "UNMITIGATED" if not ob['mitigated'] else "MITIGATED"
        print(f"[{status}] OB: {ob['bottom']:.2f} - {ob['top']:.2f} (Created: {ob['timestamp']})")

if __name__ == '__main__':
    main()

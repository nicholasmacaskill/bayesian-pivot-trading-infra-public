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
    
    df_1h = scanner.fetch_data(symbol, '1h', limit=50)
    if df_1h is None: return

    print("--- 1H FVG Detection ---")
    for i in range(2, len(df_1h)):
        # Bearish FVG (Gap down)
        if df_1h['high'].iloc[i] < df_1h['low'].iloc[i-2]:
            print(f"Bearish FVG at {df_1h['timestamp'].iloc[i]}: {df_1h['high'].iloc[i]} - {df_1h['low'].iloc[i-2]}")
        # Bullish FVG (Gap up)
        if df_1h['low'].iloc[i] > df_1h['high'].iloc[i-2]:
            print(f"Bullish FVG at {df_1h['timestamp'].iloc[i]}: {df_1h['high'].iloc[i-2]} - {df_1h['low'].iloc[i]}")

if __name__ == '__main__':
    main()

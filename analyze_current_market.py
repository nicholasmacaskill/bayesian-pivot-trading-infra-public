import os
import sys
import pandas as pd
from dotenv import load_dotenv

# Add the project root to sys.path
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner
from src.core.config import Config

def main():
    load_dotenv('.env.local')
    scanner = SMCScanner()
    symbol = "BTC/USD"
    
    print(f"--- Analyzing market structure for {symbol} ---")
    
    # 1. Fetch Data
    df_1h = scanner.fetch_data(symbol, '1h', limit=100)
    if df_1h is None:
        print("Failed to fetch 1H data.")
        return
    
    current_price = df_1h.iloc[-1]['close']
    print(f"Current Price: {current_price}")
    
    # 2. Get Price Quartiles (BSL/SSL)
    quartiles = scanner.get_price_quartiles(symbol)
    if quartiles:
        print("\nLiquidity Ranges:")
        for name, levels in quartiles.items():
            print(f"[{name}]")
            print(f"- High (BSL): {levels['high']}")
            print(f"- Low (SSL): {levels['low']}")
            print(f"- Mid (Equilibrium): {levels['mid']}")
    
    # 3. Get HTF POIs (Order Blocks / FVGs)
    pois = scanner.detect_htf_pois(symbol)
    if pois:
        print("\nHTF Gravity Points:")
        for p in pois:
            print(f"- {p['tf']} {p['type']} at {p['level']:.2f} (Zone: {p.get('bottom', 0):.2f} - {p.get('top', 0):.2f})")
    
    # 4. Check Intermarket SMT
    smt_strength = scanner.intermarket.get_smt_strength(symbol, df_1h)
    print(f"\nSMT Strength: {smt_strength:.2f}")

if __name__ == '__main__':
    main()

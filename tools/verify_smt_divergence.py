import sys
import os
import pandas as pd
import numpy as np

# Add project root to path
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner

def get_pivots(df, window=2):
    """Simple fractal detection for SMT"""
    highs = (df['high'] > df['high'].shift(1)) & (df['high'] > df['high'].shift(-1))
    lows = (df['low'] < df['low'].shift(1)) & (df['low'] < df['low'].shift(-1))
    return highs, lows

def check_smt():
    print("🕵️ Analyzing SMT Divergence (BTC vs ETH)...")
    scanner = SMCScanner()
    
    # Fetch 15m data for clearer structure
    timeframe = '1h'
    btc_df = scanner.fetch_data("BTC/USD", timeframe, limit=50)
    eth_df = scanner.fetch_data("ETH/USD", timeframe, limit=50)
    
    if btc_df is None or eth_df is None:
        print("❌ Could not fetch data for BTC or ETH")
        return

    # Find recent swing high/low for both
    btc_highs, btc_lows = get_pivots(btc_df)
    eth_highs, eth_lows = get_pivots(eth_df)
    
    # Last 2 significant swing highs
    last_btc_highs = btc_df[btc_highs].tail(2)
    last_eth_highs = eth_df[eth_highs].tail(2)
    
    if len(last_btc_highs) >= 2 and len(last_eth_highs) >= 2:
        btc_h1, btc_h2 = last_btc_highs['high'].iloc[-2], last_btc_highs['high'].iloc[-1]
        eth_h1, eth_h2 = last_eth_highs['high'].iloc[-2], last_eth_highs['high'].iloc[-1]
        
        print(f"\n📈 Bearish SMT Check (Swing Highs):")
        print(f"   BTC: {btc_h1:,.0f} -> {btc_h2:,.0f} ({'Higher High' if btc_h2 > btc_h1 else 'Lower High'})")
        print(f"   ETH: {eth_h1:,.0f} -> {eth_h2:,.0f} ({'Higher High' if eth_h2 > eth_h1 else 'Lower High'})")
        
        # Check for Divergence
        if (btc_h2 >= btc_h1 and eth_h2 < eth_h1) or (btc_h2 < btc_h1 and eth_h2 >= eth_h1):
            print("🚨 BEARISH SMT DIVERGENCE DETECTED! Institutional Trend Exhaustion.")
        else:
            print("✅ No SMT Divergence on highs.")

    # Last 2 significant swing lows
    last_btc_lows = btc_df[btc_lows].tail(2)
    last_eth_lows = eth_df[eth_lows].tail(2)
    
    if len(last_btc_lows) >= 2 and len(last_eth_lows) >= 2:
        btc_l1, btc_l2 = last_btc_lows['low'].iloc[-2], last_btc_lows['low'].iloc[-1]
        eth_l1, eth_l2 = last_eth_lows['low'].iloc[-2], last_eth_lows['low'].iloc[-1]
        
        print(f"\n📉 Bullish SMT Check (Swing Lows):")
        print(f"   BTC: {btc_l1:,.0f} -> {btc_l2:,.0f} ({'Lower Low' if btc_l2 < btc_l1 else 'Higher Low'})")
        print(f"   ETH: {eth_l1:,.0f} -> {eth_l2:,.0f} ({'Lower Low' if eth_l2 < eth_l1 else 'Higher Low'})")
        
        if (btc_l2 <= btc_l1 and eth_l2 > eth_l1) or (btc_l2 > btc_l1 and eth_l2 <= eth_l1):
            print("🚨 BULLISH SMT DIVERGENCE DETECTED! Institutional Accumulation / Trend Ending.")
        else:
            print("✅ No SMT Divergence on lows.")

    print("\n💡 Tip: SMT Divergence at Key Liquidity Levels is the #1 indicator of a trend reversal.")

if __name__ == "__main__":
    check_smt()

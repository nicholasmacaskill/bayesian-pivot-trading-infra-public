
import sys
import os
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner
import pandas as pd

def analyze_deviation():
    scanner = SMCScanner()
    symbol = "BTC/USD"
    
    print(f"\n🦁 Analyzing Price Action for {symbol}...")
    
    # Check 15m Candles for the Wick
    print("\n[15m Candles - Last 5]")
    df_15m = scanner.fetch_data(symbol, "15m", limit=5)
    for index, row in df_15m.iterrows():
        close = row['close']
        high = row['high']
        low = row['low']
        open_p = row['open']
        color = "🟢" if close >= open_p else "🔴"
        print(f"{row['timestamp']} | {color} O: {open_p:.1f} H: {high:.1f} L: {low:.1f} C: {close:.1f}")

    # Check 5m Candles for structure
    print("\n[5m Candles - Last 10]")
    df_5m = scanner.fetch_data(symbol, "5m", limit=10)
    for index, row in df_5m.iterrows():
        close = row['close']
        high = row['high']
        low = row['low']
        open_p = row['open']
        color = "🟢" if close >= open_p else "🔴"
        print(f"{row['timestamp']} | {color} O: {open_p:.1f} H: {high:.1f} L: {low:.1f} C: {close:.1f}")

    current_price = df_5m.iloc[-1]['close']
    print(f"\n💰 Current Price: {current_price}")
    
    # Check if we have a wick above 67400 but close below
    recent_high = df_5m['high'].max()
    print(f"🔥 Recent High: {recent_high}")
    
    if recent_high > 67400 and current_price < 67400:
        print("\n🚨 DEVIATION CONFIRMED: Price wicked above 67,400 and failed.")
        print("✅ Bearish Thesis Regained.")
    elif current_price > 67400:
        print("\n⚠️ BREAKOUT WARNING: Price is sustaining above 67,400.")
    else:
        print("\nℹ️ Price is below resistance, but no major swing failure detected recently.")

if __name__ == "__main__":
    analyze_deviation()

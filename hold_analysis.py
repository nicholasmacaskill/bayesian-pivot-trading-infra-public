import sys
import os
import pandas as pd
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner

def analyze_hold():
    scanner = SMCScanner()
    symbol_btc = "BTC/USD"
    symbol_eth = "ETH/USD"
    
    print(f"--- Analysis at {datetime.now()} ---")
    
    # 1. Fetch Data
    df_btc = scanner.fetch_data(symbol_btc, '5m', limit=288) # 24h
    df_eth = scanner.fetch_data(symbol_eth, '5m', limit=288)
    
    if df_btc is None or df_eth is None:
        print("Failed to fetch data.")
        return

    # 2. Asian Range (00:00 - 04:00 UTC)
    # Today's date in UTC
    today_utc = datetime.utcnow().date()
    start_utc = pd.Timestamp(datetime.combine(today_utc, datetime.min.time()))
    end_utc = start_utc + pd.Timedelta(hours=4)
    
    # Ensure index is datetime
    if not isinstance(df_btc.index, pd.DatetimeIndex):
        df_btc.index = pd.to_datetime(df_btc.index)
        df_eth.index = pd.to_datetime(df_eth.index)

    asian_btc = df_btc[(df_btc.index >= start_utc) & (df_btc.index <= end_utc)]
    if not asian_btc.empty:
        a_high = asian_btc['high'].max()
        a_low = asian_btc['low'].min()
        print(f"BTC Asian High: {a_high:.2f}")
        print(f"BTC Asian Low: {a_low:.2f}")
        
        curr_btc = df_btc['close'].iloc[-1]
        print(f"BTC Current: {curr_btc:.2f}")
        
        if curr_btc > a_low:
            print("🟢 Asian Low NOT YET SWEPT. (Logical Draw on Liquidity)")
        else:
            print("🔴 Asian Low already swept. (Take profit consideration)")
    
    # 3. SMT Divergence
    # Compare recent highs/lows
    btc_recent_low = df_btc['low'].tail(20).min()
    eth_recent_low = df_eth['low'].tail(20).min()
    
    btc_prev_low = df_btc['low'].tail(40).iloc[:20].min()
    eth_prev_low = df_eth['low'].tail(40).iloc[:20].min()
    
    # SMT: if BTC makes a lower low but ETH does not (or vice versa)
    print(f"\nBTC Recent Low: {btc_recent_low:.2f} (Prev: {btc_prev_low:.2f})")
    print(f"ETH Recent Low: {eth_recent_low:.2f} (Prev: {eth_prev_low:.2f})")
    
    if (btc_recent_low < btc_prev_low) and (eth_recent_low > eth_prev_low):
        print("⚠️ SMT BULLISH DIVERGENCE (BTC LL, ETH HL) - Risk of reversal!")
    elif (eth_recent_low < eth_prev_low) and (btc_recent_low > btc_prev_low):
        print("⚠️ SMT BULLISH DIVERGENCE (ETH LL, BTC HL) - Risk of reversal!")
    else:
        print("✅ No Bullish SMT detected. Bearish momentum likely intact.")

if __name__ == "__main__":
    analyze_hold()

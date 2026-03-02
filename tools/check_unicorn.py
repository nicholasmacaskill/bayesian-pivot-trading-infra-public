import sys
import logging
from src.engines.smc_scanner import SMCScanner
from src.core.config import Config
import pandas as pd

# Setup logging to see what's happening
logging.basicConfig(level=logging.INFO)

def audit_btc():
    try:
        scanner = SMCScanner()
        print("Fetching BTC data...")
        df = scanner.fetch_data('BTC/USDT', '5m')
        if df is None:
            print("❌ Failed to fetch data. Trying yfinance fallback...")
            # Manual fallback attempt
            import yfinance as yf
            df = yf.download('BTC-USD', period='1d', interval='5m')
            if df.empty:
                print("❌ yfinance also failed.")
                return
            df.columns = [c.lower() for c in df.columns]
            df['timestamp'] = df.index
            print("✅ Data fetched via yfinance.")

        print(f"Data shape: {df.shape}")
        
        # Check for Bearish MSS
        print("Checking for MSS...")
        mss = scanner.detect_mss(df, lookback=50)
        print(f"MSS Detected: {mss}")
        
        # Bias
        print("Calculating Bias...")
        bias = scanner.get_detailed_bias('BTC/USDT')
        print(f"Bias: {bias}")

        if mss and mss['direction'] == 'SHORT':
            # Check for FVG
            fvg = scanner.is_tapping_fvg(df, 'SHORT')
            print(f"FVG Tap in Premium: {fvg}")
            
            # Unicorn logic: Breaker + FVG
            origin_idx = mss['origin_index']
            breaker_candle = df.loc[origin_idx]
            print(f"Breaker Candle (at {origin_idx}): H={breaker_candle['high']}, L={breaker_candle['low']}")
            
            current_price = df.iloc[-1]['close']
            print(f"Current Price: {current_price}")
            
            in_breaker = current_price <= breaker_candle['high'] and current_price >= breaker_candle['low']
            print(f"In Breaker Zone: {in_breaker}")
            
            if in_breaker and fvg:
                print("🦄 UNICORN DETECTED: Price is in Breaker + FVG zone with Bearish Flow.")
            elif in_breaker:
                print("🛡️ BREAKER LEVEL: Price is at the Breaker, but FVG confluence missing.")
            elif fvg:
                print("📊 FVG PULLBACK: Price is in FVG, but Breaker level missing.")
            else:
                print("💤 Standard Bearish structure, no Unicorn confluence.")
        else:
            print("No Bearish Market Structure Shift detected in last 50 candles.")

    except Exception as e:
        print(f"💥 Error during audit: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    audit_btc()

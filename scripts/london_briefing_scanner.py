import os
import sys
import pandas as pd
import numpy as np
import ccxt
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner
from src.core.config import Config

def generate_london_briefing():
    print("🇬🇧 Bayesian Pivot: London Pre-Session Briefing")
    print(f"Time: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")
    print("="*60)
    
    scanner = SMCScanner()
    # Switch to binance for more reliable public data in CCXT
    scanner.exchange = ccxt.binance({'enableRateLimit': True})
    symbols = Config.SYMBOLS
    
    for symbol in symbols:
        try:
            print(f"\n🔍 Analyzing {symbol}...")
            
            # 1. Fetch Data
            df_htf = scanner.fetch_data(symbol, '1h', limit=100)
            df_ltf = scanner.fetch_data(symbol, '15m', limit=100)
            
            if df_htf is None or df_ltf is None:
                print(f"❌ Could not fetch data for {symbol}")
                continue
            
            # 2. HTF Bias
            bias = scanner.get_detailed_bias(symbol)
            hurst = scanner.get_hurst_exponent(df_ltf['close'].values)
            hurst_label = "Trending" if hurst > 0.55 else ("Mean-Reverting" if hurst < 0.45 else "Chop")
            
            # 3. Asia Range (00:00 - 04:00 UTC)
            # Find today's Asia session
            today = datetime.now(timezone.utc).date()
            asia_start = datetime(today.year, today.month, today.day, 0, 0, tzinfo=timezone.utc)
            asia_end = datetime(today.year, today.month, today.day, 4, 0, tzinfo=timezone.utc)
            
            # Ensure df['timestamp'] is normalized for comparison
            temp_df = df_ltf.copy()
            if temp_df['timestamp'].dt.tz is None:
                temp_df['timestamp'] = temp_df['timestamp'].dt.tz_localize(timezone.utc)
            
            asia_df = temp_df[(temp_df['timestamp'] >= asia_start) & (temp_df['timestamp'] <= asia_end)]
            
            if asia_df.empty:
                # Try yesterday if we just crossed midnight UTC
                yesterday = today - timedelta(days=1)
                asia_start = datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, tzinfo=timezone.utc)
                asia_end = datetime(yesterday.year, yesterday.month, yesterday.day, 4, 0, tzinfo=timezone.utc)
                asia_df = temp_df[(temp_df['timestamp'] >= asia_start) & (temp_df['timestamp'] <= asia_end)]

            asia_high = asia_df['high'].max()
            asia_low = asia_df['low'].min()
            current_price = df_ltf.iloc[-1]['close']
            
            # 4. Nearest POIs
            pois = scanner.detect_htf_pois(symbol) # This uses SMCScanner logic
            
            print(f"📈 Bias: {bias}")
            print(f"🧠 Regime: {hurst_label} (Hurst: {hurst:.2f})")
            print(f"🌏 Asia Range: {asia_low:.2f} - {asia_high:.2f}")
            print(f"📍 Current Price: {current_price:.2f}")
            
            # Logic: Judas Swing Potential
            if current_price > asia_high:
                print("⚠️  Price ABOVE Asia High. Watching for rejection (SFP) or trend continuation.")
            elif current_price < asia_low:
                print("⚠️  Price BELOW Asia Low. Watching for rejection (SFP) or continuation.")
            else:
                dist_high = (asia_high - current_price)
                dist_low = (current_price - asia_low)
                print(f"🎯 Target: Asia High is {dist_high:.2f} away | Asia Low is {dist_low:.2f} away")
            
            # Draw on Liquidity
            if pois:
                nearest = min(pois, key=lambda p: abs(p['level'] - current_price))
                print(f"💧 Draw on Liquidity: {nearest['level']:.2f} ({nearest['type']})")
            
            print("-" * 30)
            
        except Exception as e:
            print(f"❌ Error analyzing {symbol}: {e}")

if __name__ == "__main__":
    generate_london_briefing()

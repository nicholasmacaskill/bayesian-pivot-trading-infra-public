import sys
import os
import pandas as pd
import ccxt
from dotenv import load_dotenv

# Add the project root to the python path
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner

def check_bearish_obs():
    print("🔍 Hunting for Bearish Order Blocks (OBs) across timeframes...")
    try:
        exchange = ccxt.binance()
        symbol = "BTC/USDT"
        
        # Get Current Price
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        print(f"\n💎 BTC Current Price: ${current_price:,.2f}")

        timeframes = ['5m', '15m', '1h', '4h', '1d']
        
        for tf in timeframes:
            print(f"\n📊 Timeframe: {tf.upper()}")
            data = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=100)
            df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Simple Bearish OB Detection logic (Bot-style)
            # 1. Look for a strong Bullish candle followed by a reversal or a break of structure
            # 2. Or look for the 'Highest High' candle before a sharp drop
            
            # Find the highest point in the recent range
            max_idx = df['high'].idxmax()
            highest_high = df.loc[max_idx, 'high']
            highest_open = df.loc[max_idx, 'open']
            highest_close = df.loc[max_idx, 'close']
            
            # The 'Order Block' range
            ob_top = highest_high
            ob_bottom = min(highest_open, highest_close)
            
            if current_price >= ob_bottom and current_price <= ob_top:
                print(f"🎯 TAPPED! Price is INSIDE Bearish OB: ${ob_bottom:,.2f} - ${ob_top:,.2f}")
            elif current_price > ob_top:
                print(f"🔥 BREACHED! Price is ABOVE Bearish OB: ${ob_top:,.2f} (Likely mitigated/failed)")
            else:
                distance = ((ob_bottom / current_price) - 1) * 100
                print(f"⏳ SHADOWED: Nearest Bearish OB at ${ob_bottom:,.2f}. Distance: {distance:+.2f}%")

    except Exception as e:
        print(f"🚨 Error: {e}")

if __name__ == "__main__":
    check_bearish_obs()

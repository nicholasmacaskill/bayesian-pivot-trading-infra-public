import sys
import os
import pandas as pd
import numpy as np

# Add the project root to the python path
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner

def find_liquidity():
    print("🔍 Scanning for Liquidity Pools (Draw on Liquidity)...")
    try:
        scanner = SMCScanner()
        symbol = "BTC/USD"
        
        # Get Current Price
        df_now = scanner.exchange.fetch_ohlcv(symbol, timeframe='1m', limit=1)
        current_price = df_now[-1][4]
        print(f"\n💎 Current Price: ${current_price:,.2f}")

        # Fetch 6H and 1H data
        timeframes = ['6h', '1h']
        
        for tf in timeframes:
            print(f"\n📊 Timeframe: {tf.upper()}")
            df_raw = scanner.exchange.fetch_ohlcv(symbol, timeframe=tf, limit=100)
            # Convert to DataFrame for easier handling
            df = pd.DataFrame(df_raw, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Find Pattern Swing Lows (Liquidity Pools)
            # Simple fractal: Low < prev_low AND Low < next_low (Fractal Low)
            # We want widely spaced ones, so maybe 2 candle buffer?
            
            # Using simple 3-candle fractal for speed
            df['is_low'] = (df['low'] < df['low'].shift(1)) & (df['low'] < df['low'].shift(-1))
            df['is_high'] = (df['high'] > df['high'].shift(1)) & (df['high'] > df['high'].shift(-1))
            
            # Filter for Lows below current price (Sell Side Liquidity - SSL)
            swing_lows = df[df['is_low'] & (df['low'] < current_price)]
            
            # Filter for Highs above current price (Buy Side Liquidity - BSL)
            swing_highs = df[df['is_high'] & (df['high'] > current_price)]
            
            if not swing_lows.empty:
                # Nearest SSL
                nearest_ssl = swing_lows.iloc[-1] # Most recent valid swing low? 
                # Actually we want the one closest in PRICE usually, or the most recent un-swept one?
                # "Draw on Liquidity" is usually the nearest unmitigated swing point.
                # Simplified: The most recent Swing Low that is strictly below price.
                
                print(f"🔴 Nearest Sell-Side Liquidity (SSL): ${nearest_ssl['low']:,.2f}")
                # Check distance
                dist = ((current_price - nearest_ssl['low']) / current_price) * 100
                print(f"   Distance: -{dist:.2f}%")
            else:
                print("   No immediate SSL found in recent data.")

            if not swing_highs.empty:
                nearest_bsl = swing_highs.iloc[-1]
                print(f"🟢 Nearest Buy-Side Liquidity (BSL): ${nearest_bsl['high']:,.2f}")
                dist = ((nearest_bsl['high'] - current_price) / current_price) * 100
                print(f"   Distance: +{dist:.2f}%")

    except Exception as e:
        print(f"🚨 Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    find_liquidity()

import sys
import os
import pandas as pd

# Add the project root to the python path
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner

def find_invalidation():
    print("🔍 Analyzing Market Structure for Invalidation Levels...")
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
            # Use fetch_ohlcv directly
            data = scanner.exchange.fetch_ohlcv(symbol, timeframe=tf, limit=50)
            df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Find Swing Highs (Fractals)
            # High > Prev High & High > Next High
            df['is_high'] = (df['high'] > df['high'].shift(1)) & (df['high'] > df['high'].shift(-1))
            
            # Filter for Swing Highs ABOVE current price (Potential Invalidation Points)
            swing_highs = df[df['is_high'] & (df['high'] > current_price)]
            
            if not swing_highs.empty:
                # The "Controlling" Lower High is often the most recent one
                # OR the one that initiated the break of structure.
                # Here we just list the recent ones.
                
                recent_high = swing_highs.iloc[-1]
                print(f"🛑 Nearest Swing High (Potential Invalidation): ${recent_high['high']:,.2f}")
                
                # Check 2nd most recent if close
                if len(swing_highs) > 1:
                    prev_high = swing_highs.iloc[-2]
                    print(f"   Previous Swing High: ${prev_high['high']:,.2f}")
            else:
                print("   No recent Swing Highs found above price.")

    except Exception as e:
        print(f"🚨 Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    find_invalidation()

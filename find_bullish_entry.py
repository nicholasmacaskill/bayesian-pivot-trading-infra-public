import sys
import os
import pandas as pd
import ccxt

# Add the project root to the python path
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner

def find_bullish_entry():
    print("🔍 Scanning for Bullish FVG & Order Block Entries (Pullback hunt)...")
    try:
        # Force Binance for stability
        exchange = ccxt.binance()
        symbol = "BTC/USDT"
        
        # Get Current Price
        ticker = exchange.fetch_ticker(symbol)
        current_price = ticker['last']
        print(f"\n💎 BTC Current Price: ${current_price:,.2f}")

        timeframes = ['5m', '15m', '1h']
        
        for tf in timeframes:
            print(f"\n📊 Timeframe: {tf.upper()}")
            data = exchange.fetch_ohlcv(symbol, timeframe=tf, limit=100)
            df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # 1. Find Bullish FVGs (Gaps in price)
            # Gap between candle (i-2) high and candle (i) low
            for i in range(2, len(df)):
                c2_high = df.loc[i-2, 'high']
                c0_low = df.loc[i, 'low']
                
                if c0_low > c2_high:
                    fvg_bottom = c2_high
                    fvg_top = c0_low
                    
                    # Only show if BELOW current price (for pullback)
                    if fvg_top < current_price:
                        distance = ((fvg_top / current_price) - 1) * 100
                        print(f"📦 BULLISH FVG: ${fvg_bottom:,.2f} - ${fvg_top:,.2f} ({distance:+.2f}%)")

            # 2. Find Bullish Order Blocks (Last down candle before up move)
            # Look for recent swing lows
            df['is_low'] = (df['low'] < df['low'].shift(1)) & (df['low'] < df['low'].shift(-1))
            swing_lows = df[df['is_low']]
            if not swing_lows.empty:
                recent_low = swing_lows.iloc[-1]
                if recent_low['close'] < current_price:
                    print(f"🛡️ RECENT SWING LOW (Support): ${recent_low['low']:,.2f}")

    except Exception as e:
        print(f"🚨 Error: {e}")

if __name__ == "__main__":
    find_bullish_entry()

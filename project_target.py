import sys
import os
import pandas as pd

# Add the project root to the python path
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner

def project_target():
    print("🔮 Projecting Timeline to $60,000...")
    try:
        scanner = SMCScanner()
        symbol = "BTC/USD"
        target_price = 60000
        
        # Get Daily Data for ATR
        df_1d_raw = scanner.exchange.fetch_ohlcv(symbol, timeframe='1d', limit=30)
        df = pd.DataFrame(df_1d_raw, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        
        current_price = df['close'].iloc[-1]
        
        # Calculate ATR (14)
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['close'].shift(1))
        df['tr3'] = abs(df['low'] - df['close'].shift(1))
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        df['atr'] = df['tr'].rolling(window=14).mean()
        
        current_atr = df['atr'].iloc[-1]
        
        print(f"\n💎 Current Price: ${current_price:,.2f}")
        print(f"📉 Target Price: ${target_price:,.2f}")
        print(f"📊 Daily Volatility (ATR-14): ${current_atr:,.2f}")
        
        distance = current_price - target_price
        
        if distance <= 0:
            print("✅ Price is already at or below target!")
            return

        print(f"📏 Distance to Target: ${distance:,.2f} ({ (distance/current_price)*100 :.2f}%)")
        
        # Scenarios
        # 1. Normal Volatility (1 ATR/day drop) - Unlikely to be straight line
        days_normal = distance / current_atr
        
        # 2. High Momentum (2 ATR/day drop) - Crash/Correction mode
        days_fast = distance / (current_atr * 2)
        
        # 3. Grind (0.5 ATR/day net move)
        days_slow = distance / (current_atr * 0.5)
        
        print(f"\n⏳ ESTIMATED TIMELINE:")
        print(f"   🚀 High Velocity (Crash): ~{days_fast:.1f} Days")
        print(f"   🚶 Normal Trend: ~{days_normal:.1f} Days")
        print(f"   🐌 Slow Grind: ~{days_slow:.1f} Days")

    except Exception as e:
        print(f"🚨 Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    project_target()

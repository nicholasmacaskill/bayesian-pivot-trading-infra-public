import sys
import os

# Add the project root to the python path
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner
from src.core.config import Config

def check_btc():
    print("🔍 Initializing SMC Scanner for BTC/USD...")
    try:
        scanner = SMCScanner()
        symbol = "BTC/USD"
        
        # 0. Get Current Price
        df_5m_ohlcv = scanner.exchange.fetch_ohlcv(symbol, timeframe='5m', limit=1)
        current_price = df_5m_ohlcv[-1][4]
        print(f"\n💎 Current Price: ${current_price:,.2f}")

        # 1. Check Biases
        print(f"Timeframe: 4H")
        bias_4h = scanner.get_4h_bias(symbol)
        print(f"📉 4H Bias Score: {bias_4h}")
        
        # 2. Key HTF Level Research (Looking for the 63k magnet)
        print(f"\n🔎 Searching for HTF Magnets (1D/4H/1H)...")
        # Fetch data
        df_1h = scanner.exchange.fetch_ohlcv(symbol, timeframe='1h', limit=100)
        
        # Look for Bullish FVG in the 63k-64k range (Potential Draw)
        gaps_63k = []
        for i in range(2, len(df_1h)):
            # Bullish FVG: High of candle i-2 < Low of candle i
            if df_1h[i-2][2] < df_1h[i][3]: # h_i-2 < l_i
                gap_top = df_1h[i][3]
                gap_bottom = df_1h[i-2][2]
                if 62500 <= gap_top <= 64500:
                    gaps_63k.append((gap_bottom, gap_top))
        
        if gaps_63k:
            print(f"🧲 FVG DETECTED in 63k Zone: {gaps_63k[0]}")
        else:
            print("❌ No specific FVGs found right at 63k (1H).")

        # Major HTF Swing Low
        df_1d = scanner.exchange.fetch_ohlcv(symbol, timeframe='1d', limit=100)
        recent_lows = [d[3] for d in df_1d[-30:]]
        ma_low = min(recent_lows)
        print(f"📍 Major HTF Swing Low: ${ma_low:,.2f}")
        
        # 3. Check 5m Pattern
        print(f"\nTimeframe: 5m (Scanning for patterns...)")
        result = scanner.scan_pattern(symbol, timeframe="5m")
        if result:
            setup, df = result
            print(f"✅ PATTERN FOUND: {setup.get('pattern')}")
            print(f"   Bias: {setup.get('bias')}")
        else:
            print("❌ No immediate 5m SMC Patterns.")
            
        # 3. Check Order Flow
        print(f"\nTimeframe: 5m (Checking Order Flow...)")
        flow_result = scanner.scan_order_flow(symbol, timeframe="5m")
        if flow_result:
             setup, df = flow_result
             print(f"🌊 ORDER FLOW SIGNAL: {setup.get('pattern')}")
             print(f"   Bias: {setup.get('bias')}")
             print(f"   Signal: {setup.get('side')}")
        else:
             print("❌ No Order Flow Signals found.")

    except Exception as e:
        print(f"🚨 Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_btc()


import sys
import os
import pandas as pd

# Add the project root to the python path
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner

def get_current_play():
    print("🚀 SovereignSMC Tactical Briefing")
    print("=================================")
    try:
        scanner = SMCScanner()
        symbol = "BTC/USD"
        
        # 1. Fetch Data
        df = scanner.fetch_data(symbol, '1h', limit=100)
        current_price = df['close'].iloc[-1]
        print(f"💎 Current Price: ${current_price:,.2f}")
        
        # 2. Get HTF Bias
        bias = scanner.get_detailed_bias(symbol)
        print(f"📊 Market Bias: {bias}")
        
        # 3. Find SSL/BSL
        print("\n🎯 Immediate Magnets:")
        
        # 1H Liquidity
        df['is_low'] = (df['low'] < df['low'].shift(1)) & (df['low'] < df['low'].shift(-1))
        df['is_high'] = (df['high'] > df['high'].shift(1)) & (df['high'] > df['high'].shift(-1))
        
        ssl_df = df[df['is_low'] & (df['low'] < current_price)]
        bsl_df = df[df['is_high'] & (df['high'] > current_price)]
        
        if not ssl_df.empty:
            ssl = ssl_df['low'].iloc[-1]
            print(f"🔴 Sell-Side Liquidity (SSL): ${ssl:,.2f}")
        else:
            # Fallback to HTF (4H) Search
            print("⚠️ No immediate 1H SSL detected (Current Lows). Searching 4H...")
            df_4h = scanner.fetch_data(symbol, '4h', limit=200)
            df_4h['is_low'] = (df_4h['low'] < df_4h['low'].shift(1)) & (df_4h['low'] < df_4h['low'].shift(-1))
            ssl_4h_df = df_4h[df_4h['is_low'] & (df_4h['low'] < current_price)]
            if not ssl_4h_df.empty:
                ssl = ssl_4h_df['low'].iloc[-1]
                print(f"🔴 HTF Sell-Side Liquidity (SSL): ${ssl:,.2f}")
            else:
                print("🔴 Major Target: $60,001 (Psychological/6H Pool)")

        if not bsl_df.empty:
            bsl = bsl_df['high'].iloc[-1]
            print(f"🟢 Buy-Side Liquidity (BSL): ${bsl:,.2f}")
        
        # 4. Check for FVGs
        print("\n🧲 Value Gaps (Targets):")
        # Bullish FVG below (Maget for shorts)
        for i in range(len(df)-3, 0, -1):
            if df.iloc[i-2]['high'] < df.iloc[i]['low']:
                gap_top = df.iloc[i]['low']
                gap_bottom = df.iloc[i-2]['high']
                if gap_top < current_price:
                    print(f"🔸 Bullish FVG below: ${gap_bottom:,.2f} - ${gap_top:,.2f}")
                    break
        
        # Bearish FVG above (Magnet for longs)
        for i in range(len(df)-3, 0, -1):
            if df.iloc[i-2]['low'] > df.iloc[i]['high']:
                gap_bottom = df.iloc[i]['high']
                gap_top = df.iloc[i-2]['low']
                if gap_bottom > current_price:
                    print(f"🔹 Bearish FVG above: ${gap_bottom:,.2f} - ${gap_top:,.2f}")
                    break
                    
        print("\n💡 Strategy: ")
        if "BEARISH" in bias:
            print("- Heavy selling pressure. Trend is Bearish.")
            print(f"- Look for a sweep of SSL at ${ssl:,.2f}, OR a retest of the Bearish FVG above.")
            print("- Avoid 'NY Noise' into the close. Prime plays occur at London.")
        else:
            print("- Market is consolidating or showing signs of recovery.")
            
    except Exception as e:
        print(f"🚨 Tactical Error: {e}")

if __name__ == "__main__":
    get_current_play()

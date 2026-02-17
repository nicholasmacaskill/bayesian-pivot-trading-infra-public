import sys
import os
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner
from src.engines.sentiment_engine import SentimentEngine
from src.core.config import Config

def check_btc():
    print("🦁 Sovereign System: Analyzing BTC/USD for Short Hold...")
    
    scanner = SMCScanner()
    sentiment = SentimentEngine()
    
    symbol = "BTC/USD"
    
    # 1. Get Bias
    bias = scanner.get_detailed_bias(symbol, visual_check=False)
    print(f"\n🔍 System Bias: {bias}")
    
    # 2. Get Quartiles
    quartiles = scanner.get_price_quartiles(symbol)
    if quartiles:
        print("\n📊 Liquidity Levels:")
        print(f"   Asian Low: {quartiles['Asian Range']['low']:.2f}")
        print(f"   Asian High: {quartiles['Asian Range']['high']:.2f}")
        if 'London Range' in quartiles:
            print(f"   London Low: {quartiles['London Range']['low']:.2f}")
    
    # 3. Get Current Price
    df = scanner.fetch_data(symbol, "5m", limit=10)
    current_price = df['close'].iloc[-1]
    print(f"\n💰 Current Price: {current_price:.2f}")
    
    # 4. Check for Reversal Signs (Hurst)
    hurst = scanner.get_hurst_exponent(df['close'].values)
    print(f"📉 Hurst Exponent: {hurst:.2f} ({'Mean Reverting' if hurst < 0.5 else 'Trending'})")
    
    # 5. Recommendation Logic
    print("\n🧠 System Logic:")
    if "BEARISH" in bias:
        print("   ✅ Bias is BEARISH. Trend supports holding.")
    else:
        print("   ⚠️ Bias is BULLISH/NEUTRAL. Be careful.")
        
    if hurst < 0.4:
        print("   ⚠️ Market is Mean Reverting. Expect chop/pullback.")
    
if __name__ == "__main__":
    check_btc()

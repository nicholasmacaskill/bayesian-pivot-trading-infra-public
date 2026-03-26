import sys
import os
import pandas as pd
from datetime import datetime, timezone

# Fix ModuleNotFoundError
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner
from src.core.config import Config

def analyze_full_context():
    scanner = SMCScanner()
    
    # 0. Bypass Synchrony globally in this session
    original_fetch = scanner.fetch_data
    def patched_fetch(*args, **kwargs):
        kwargs['synchronized'] = False
        return original_fetch(*args, **kwargs)
    scanner.fetch_data = patched_fetch
    
    symbol = "BTC/USD"
    
    # 1. Fetch MTF Data
    df_1m = scanner.fetch_data(symbol, "1m", limit=100)
    df_5m = scanner.fetch_data(symbol, "5m", limit=300)
    df_1h = scanner.fetch_data(symbol, "1h", limit=100)
    df_4h = scanner._aggregate_ohlcv(scanner.fetch_data(symbol, "1h", limit=400), "4h")
    
    if df_1m is None or df_5m is None:
        print("❌ Error: Could not fetch data stream.")
        return

    current_price = df_1m['close'].iloc[-1]
    
    # 2. Institutional Analysis
    hurst = scanner.get_hurst_exponent(df_5m['close'].values)
    quartile_data = scanner.get_session_quartile()
    price_ranges = scanner.get_price_quartiles(symbol) or {}
    pois = scanner.detect_htf_pois(symbol)
    
    # 3. Bias Analysis
    def get_tf_bias(df):
        if df is None or len(df) < 5: return 0
        ema20 = df['close'].ewm(span=20).mean().iloc[-1]
        ema50 = df['close'].ewm(span=50).mean().iloc[-1]
        return 1 if ema20 > ema50 else -1

    bias_4h = get_tf_bias(df_4h)
    bias_1h = get_tf_bias(df_1h)
    bias_5m = get_tf_bias(df_5m)
    
    # 4. SMT & Context
    market_context = scanner.intermarket.get_market_context()
    smt_strength = scanner.intermarket.get_smt_strength(symbol, df_5m)
    
    # OUTPUT
    print("\n" + "═"*60)
    print(f"🏛️  SOVEREIGN MARKET STRUCTURE REPORT | {symbol}")
    print("═"*60)
    print(f"💰 PRICE:            ${current_price:,.2f}")
    print(f"🌀 HURST (PHYSICS):   {hurst:.2f} ({'Trending' if hurst > 0.55 else 'Reverting' if hurst < 0.45 else 'Random'})")
    print(f"🕒 SESSION PHASE:    {quartile_data['phase']}")
    print(f"🏛️  BIAS (4H/1H/5M):  {bias_4h} / {bias_1h} / {bias_5m}")
    print(f"⚡ SMT SPONSORSHIP:  {smt_strength:.2f}/1.0")
    print("─"*60)
    
    print("📊 LIQUIDITY TARGETS (MAGNETS):")
    if "Asian Range" in price_ranges:
        ar = price_ranges["Asian Range"]
        print(f"  • [Asian High]       ${ar['high']:,.2f}")
        print(f"  • [Asian Low]        ${ar['low']:,.2f}")
    if "London Range" in price_ranges:
        lr = price_ranges["London Range"]
        print(f"  • [London High]      ${lr['high']:,.2f}")
        print(f"  • [London Low]       ${lr['low']:,.2f}")
    
    print("\n🔮 GRAVITY POINTS (HTF POIs):")
    for poi in pois[:3]:
        print(f"  • {poi['type']} ({poi['tf']}):  ${poi['level']:,.2f}")
        
    print("\n🧠 STRATEGIC DIRECTIVE:")
    if bias_4h == 1 and bias_1h == 1:
        if current_price < price_ranges.get("Asian Range", {}).get("mid", 0):
            print("  ✅ LOOK FOR: Bullish MSS at Asian/London Low (Discount Buy).")
        else:
            print("  ⚠️ LOOK FOR: Expansion continuation above Asian High.")
    elif bias_4h == -1 and bias_1h == -1:
        print("  ✅ LOOK FOR: Bearish rejection at Asian Range Premium/High.")
    else:
        print("  ⚠️ LOOK FOR: Consolidation sweep. Session phase suggests waiting for Q2/Q3 shift.")
    print("═"*60)

if __name__ == "__main__":
    analyze_full_context()

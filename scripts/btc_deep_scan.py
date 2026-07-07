import sys
import os
import time
from datetime import datetime, timezone

# Fix ModuleNotFoundError
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner
from src.engines.sentiment_engine import SentimentEngine
from src.core.config import Config

def run_deep_scan():
    print("🏛️ Sovereign System: Initializing Deep Institutional Scan | BTC/USD")
    
    scanner = SMCScanner()
    # Bypass synchrony for manual briefing
    original_fetch = scanner.fetch_data
    def patched_fetch(*args, **kwargs):
        kwargs['synchronized'] = False
        return original_fetch(*args, **kwargs)
    scanner.fetch_data = patched_fetch
    
    sentiment_engine = SentimentEngine()
    symbol = "BTC/USD"
    
    # 1. Fetch Context
    df_1h = scanner.fetch_data(symbol, "1h", limit=200)
    df_5m = scanner.fetch_data(symbol, "5m", limit=300)
    
    # 1b. Fetch REAL-TIME Ticker (Fix for price latency)
    ticker = scanner.exchange.fetch_ticker(symbol)
    current_price = ticker['last']
    
    if df_1h is None or df_5m is None:
        print("❌ Error: Connectivity issues for BTC stream.")
        return

    
    # 2. HTF Bias & POIs
    # Manually aggregate 4H for Coinbase
    df_1h_for_4h = scanner.fetch_data(symbol, "1h", limit=400)
    df_4h = scanner._aggregate_ohlcv(df_1h_for_4h, "4h")
    
    # Calculate bias using available TFs since get_detailed_bias might hit 4h limit
    def get_tf_bias(df):
        if df is None or len(df) < 5: return 0
        ema20 = df['close'].ewm(span=20).mean().iloc[-1]
        ema50 = df['close'].ewm(span=50).mean().iloc[-1]
        return 1 if ema20 > ema50 else -1

    bias_4h = get_tf_bias(df_4h)
    bias_1h = get_tf_bias(df_1h)
    bias_label = f"{'BULLISH' if bias_4h == 1 and bias_1h == 1 else 'BEARISH' if bias_4h == -1 and bias_1h == -1 else 'NEUTRAL'} (4H: {bias_4h}, 1H: {bias_1h})"
    
    pois = scanner.detect_htf_pois(symbol)
    
    # 3. Session & Price Quartiles
    session_data = scanner.get_session_quartile()
    price_ranges = scanner.get_price_quartiles(symbol)
    
    # 4. Institutional Confluence
    market_context = scanner.intermarket.get_market_context()
    smt_strength = scanner.intermarket.get_smt_strength(symbol, df_5m)
    hurst = scanner.get_hurst_exponent(df_5m['close'].values)
    
    # 5. Sentiment
    sentiment_data = sentiment_engine.get_market_sentiment(symbol)
    sentiment_str = f"F&G: {sentiment_data['fear_and_greed']} | News: {sentiment_data['news_sentiment'][:50]}..."
    
    # Formatting
    print("\n" + "═"*60)
    print(f"🏛️  SOVEREIGN DEEP SCAN | {symbol} | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("═"*60)
    print(f"💰 PRICE:         ${current_price:,.2f}")
    print(f"🏗️  BIAS (SMC):    {bias_label}")
    print(f"🕒 ICT PHASE:      {session_data['phase']} (Q{session_data['num']})")
    print(f"🌀 HURST REGIME:   {hurst:.3f} | {'EXPANSION' if hurst > 0.55 else 'REVERSION' if hurst < 0.45 else 'CONSOLIDATION'}")
    print(f"⚡ SMT STRENGTH:   {smt_strength:.2f}/1.0")
    print(f"📉 SENTIMENT:      {sentiment_str}")
    print("─"*60)
    
    if price_ranges:
        print("🎯 PRICE QUARTILES:")
        for name, r in price_ranges.items():
            pos = (current_price - r['low']) / (r['high'] - r['low']) if (r['high'] - r['low']) != 0 else 0.5
            zone = "DEEP DISCOUNT" if pos < 0.25 else "DISCOUNT" if pos < 0.5 else "PREMIUM" if pos < 0.75 else "DEEP PREMIUM"
            print(f"  • {name:15}: ${r['low']:,.0f} - ${r['high']:,.0f} | Pos: {pos:.2%} ({zone})")
    
    if pois:
        print("\n🧲 GRAVITY POINTS (HTF POIs):")
        # Sort by distance
        pois_sorted = sorted(pois, key=lambda p: abs(p['level'] - current_price))[:3]
        for p in pois_sorted:
            dist = (p['level'] - current_price) / current_price
            direction = "ABOVE" if dist > 0 else "BELOW"
            print(f"  • {p['type']:12} at ${p['level']:,.2f} ({abs(dist):.2%} {direction})")
            
    print("═"*60)
    print("🧠 SOVEREIGN SYNOPSIS:")
    if "BULLISH" in bias_label and session_data['num'] in [1, 2]:
        print("  • Accumulation/Manipulation phase in Bullish HTF bias.")
        print("  • Watch for Judas Swing below Asian Low / PDL to induce shorts before expansion.")
    elif "BEARISH" in bias_label and session_data['num'] in [1, 2]:
        print("  • Distribution/Manipulation phase in Bearish HTF bias.")
        print("  • Watch for Judas Swing above Asian High / PDH to induce longs before decline.")
    else:
        print("  • Market is in Distribution/Continuation phase.")
        print("  • High probability trades require extreme quartile alignment or SMT divergence spikes.")
    
    if hurst < 0.45:
        print("  • Low Hurst detected: Favor Turtle Soup (Liquidity Sweep & Reversal) setups.")
    elif hurst > 0.55:
        print("  • High Hurst detected: Favor Breaker Block or FVG Expansion setups.")
    print("═"*60)

if __name__ == "__main__":
    run_deep_scan()

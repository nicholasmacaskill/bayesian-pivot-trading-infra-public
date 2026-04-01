import sys
import os
import time
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

# Fix ModuleNotFoundError
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner
from src.engines.sentiment_engine import SentimentEngine
from src.core.config import Config
from src.engines.ai_validator import AIValidator

def predict_btc_5m():
    print("🧠 Sovereign System: Generating 5-Minute BTC/USD Expectation...")
    
    scanner = SMCScanner()
    
    # 0. Monkey-patch fetch_data to always bypass synchrony check
    original_fetch = scanner.fetch_data
    def patched_fetch(*args, **kwargs):
        kwargs['synchronized'] = False
        return original_fetch(*args, **kwargs)
    scanner.fetch_data = patched_fetch
    
    sentiment_engine = SentimentEngine()
    validator = AIValidator()
    
    symbol = "BTC/USD"
    
    # 1. Fetch Multi-Timeframe Data (Bypass synchrony for manual scan)
    df_1m = scanner.fetch_data(symbol, "1m", limit=60, synchronized=False)
    df_5m = scanner.fetch_data(symbol, "5m", limit=100, synchronized=False)
    if df_1m is None or df_5m is None:
        print("❌ Error: Could not fetch data stream.")
        return

    current_price = df_1m['close'].iloc[-1]
    last_1m_vol = df_1m['volume'].iloc[-1]
    
    # 2. Institutional Context (9-Gate Logic)
    # Manually handle bias because Coinbase lacks native 4h
    df_1h = scanner.fetch_data(symbol, "1h", limit=100)
    df_4h = scanner._aggregate_ohlcv(scanner.fetch_data(symbol, "1h", limit=400), "4h")
    
    # Calculate bias manually since get_detailed_bias might fail on 4h gap
    def get_tf_bias(df):
        if df is None or len(df) < 5: return 0
        ema20 = df['close'].ewm(span=20).mean().iloc[-1]
        ema50 = df['close'].ewm(span=50).mean().iloc[-1]
        return 1 if ema20 > ema50 else -1

    bias_4h = get_tf_bias(df_4h)
    bias_1h = get_tf_bias(df_1h)
    bias_5m = get_tf_bias(df_5m)
    
    bias_label = "NEUTRAL"
    if bias_4h == 1 and bias_1h == 1: bias_label = "BULLISH"
    elif bias_4h == -1 and bias_1h == -1: bias_label = "BEARISH"
    
    hurst = scanner.get_hurst_exponent(df_5m['close'].values)
    quartile_data = scanner.get_session_quartile()
    pois = scanner.detect_htf_pois(symbol)
    market_context = scanner.intermarket.get_market_context()
    smt_strength = scanner.intermarket.get_smt_strength(symbol, df_5m)
    
    # 3. Market Regime Labeling
    regime = "CHOP"
    if hurst > 0.55: regime = "EXPANSION (Momentum)"
    elif hurst < 0.45: regime = "MEAN REVERSION (Range)"
    
    # 4. 5-Minute Projection Logic (Bayesian Physics)
    # Institutional logic: In Q2 (Manipulation), expect a Judas swing (false move).
    # In Q3 (Distribution), expect trend continuation.
    # Hurst > 0.55 + Strong Bias = Volatility continuation.
    
    prediction = "NEUTRAL"
    confidence = 0.5
    projected_change = 0.0
    reasoning = []

    # Bias Alignment
    if "BULLISH" in bias_label:
        projected_change += 0.0003 # Reduced for conservative local estimate
    elif "BEARISH" in bias_label:
        projected_change -= 0.0003

    # Hurst Regime
    if hurst > 0.55:
        projected_change *= 1.5 # Accelerate trend
        reasoning.append(f"Persistence detected (Hurst: {hurst:.2f})")
    elif hurst < 0.45:
        projected_change *= -0.5 # Expect reversion
        reasoning.append(f"Mean reversion expected (Hurst: {hurst:.2f})")

    # SMT Divergence
    if smt_strength > 0.6:
        projected_change *= 1.2
        reasoning.append(f"Strong SMT Sponsorship ({smt_strength:.2f})")

    # POI Gravity
    nearest_poi = None
    if pois:
        nearest_poi = min(pois, key=lambda p: abs(p['level'] - current_price))
        dist_pct = abs(nearest_poi['level'] - current_price) / current_price
        if dist_pct < 0.002: # Within 0.2%
            reasoning.append(f"Approaching HTF {nearest_poi['type']} at {nearest_poi['level']:.2f}")
            # Gravity pull
            if nearest_poi['level'] > current_price: projected_change += 0.0002
            else: projected_change -= 0.0002

    # Final Synthesis
    if projected_change > 0.0001:
        prediction = "BULLISH"
    elif projected_change < -0.0001:
        prediction = "BEARISH"
    else:
        prediction = "NEUTRAL"

    projected_price = current_price * (1 + projected_change)
    
    # 5. Output Sovereign Briefing
    print("\n" + "═"*50)
    print(f"🏛️  SOVEREIGN BRIEFING | {symbol}")
    print("═"*50)
    print(f"💰 CURRENT PRICE:  ${current_price:,.2f}")
    print(f"🎯 EXPECTED (5M):  ${projected_price:,.2f} ({prediction})")
    print(f"📈 PROJECTED Δ:    {projected_change:+.4%}")
    print("─"*50)
    print(f"🌀 REGIME:         {regime}")
    print(f"🏛️  BIAS:           {bias_label} (4H: {bias_4h}, 1H: {bias_1h})")
    print(f"🕒 ICT PHASE:       {quartile_data['phase']}")
    print(f"⚡ SMT STRENGTH:    {smt_strength:.2f}/1.0")
    print("─"*50)
    print("🧠 LOGIC:")
    for r in reasoning:
        print(f"  • {r}")
    if "BULLISH" in prediction:
        print("  • Order flow suggests institutional accumulation.")
    elif "BEARISH" in prediction:
        print("  • Order flow suggests institutional distribution.")
    else:
        print("  • High entropy detected. Expect sideways consolidation.")
    print("═"*50)

if __name__ == "__main__":
    predict_btc_5m()

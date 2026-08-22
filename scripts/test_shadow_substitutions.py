import os
import sys
import json
import yfinance as yf
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.engines.shadow_substitution_engine import ShadowSubstitutionEngine

def test_shadow():
    print("\n=======================================================")
    print(" 🧪 RUNNING SHADOW SUBSTITUTION ENGINE TEST ON LIVE BARS")
    print("=======================================================\n")
    
    engine = ShadowSubstitutionEngine()
    symbols = ["BTC-USD", "ETH-USD"]
    
    for ticker_sym in symbols:
        print(f"--- Fetching 5m data for {ticker_sym} ---")
        ticker = yf.Ticker(ticker_sym)
        df = ticker.history(period="2d", interval="5m")
        if df.empty:
            print(f"❌ Failed to fetch data for {ticker_sym}")
            continue
            
        df.columns = [c.lower() for c in df.columns]
        
        # Test evaluating both SHORT and LONG shadow metrics
        norm_sym = ticker_sym.replace("-", "/")
        short_audit = engine.run_shadow_audit(norm_sym, df, candidate_direction="SHORT")
        long_audit = engine.run_shadow_audit(norm_sym, df, candidate_direction="LONG")
        
        print(f"\n📊 [{norm_sym}] SHORT SHADOW AUDIT:")
        print(json.dumps(short_audit, indent=2))
        
        print(f"\n📊 [{norm_sym}] LONG SHADOW AUDIT:")
        print(json.dumps(long_audit, indent=2))
        print("-------------------------------------------------------")

if __name__ == "__main__":
    test_shadow()

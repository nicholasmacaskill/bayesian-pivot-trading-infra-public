import pandas as pd
import numpy as np
from visualizer import generate_ict_chart
from ai_validator import AIValidator
import os
from datetime import datetime

def test_pipeline():
    print("🧪 Starting Automated Vision Pipeline Test...")
    
    # 1. Create Mock Data (100 candles)
    dates = pd.date_range(datetime.now(), periods=100, freq='5min')
    df = pd.DataFrame({
        'timestamp': dates,
        'open': np.random.uniform(40000, 41000, 100),
        'high': np.random.uniform(40000, 41000, 100),
        'low': np.random.uniform(40000, 41000, 100),
        'close': np.random.uniform(40000, 41000, 100)
    })
    
    setup = {
        'symbol': 'BTC/USDT',
        'pattern': 'Bullish PO3 (Judas Swing)',
        'bias': 'BULLISH',
        'entry': 40500,
        'target': 41500,
        'stop_loss': 40200,
        'time_quartile': {'num': 2, 'phase': 'Q2: Manipulation (Judas)'},
        'is_discount': True,
        'smt_strength': 0.8,
        'cross_asset_divergence': 0.5
    }
    
    # 2. Test Visualization
    print("📸 Generating Chart...")
    chart_path = "test_setup_vision.png"
    generate_ict_chart(df, setup, output_path=chart_path)
    if os.path.exists(chart_path):
        print(f"✅ Chart generated: {chart_path}")
    else:
        print("❌ Chart generation FAILED.")
        return

    # 3. Test AI Validation (Vision)
    print("🤖 Calling Gemini Vision Gatekeeper...")
    validator = AIValidator(api_key="MOCK") 
    
    try:
        # Use MOCK if no key found to ensure logic check passes
        if not os.environ.get("GEMINI_API_KEY"):
             print("⚠️ No API key found, using simulated response.")
             validator.api_key = "MOCK"
        
        result = validator.analyze_trade(setup, "Low Fear", "Whale Accumulation", image_path=chart_path)
        print(f"✅ AI Analysis Success!")
        print(f"Score: {result.get('score')}")
        print(f"Verdict: {result.get('verdict')}")
        print(f"Reasoning: {result.get('reasoning')[:100]}...")
    except Exception as e:
        print(f"❌ AI Validation FAILED: {e}")

    # Cleanup
    # if os.path.exists(chart_path):
    #     os.remove(chart_path)
    
    print("🏁 Pipeline Verification Complete.")

if __name__ == "__main__":
    test_pipeline()

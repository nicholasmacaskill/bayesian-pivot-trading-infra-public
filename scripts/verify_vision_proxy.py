import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.engines.visualizer import generate_ict_chart
from src.engines.ai_validator import validate_setup

def verify_vision_proxy():
    print("🔬 Verifying VLM Vision Proxy...")
    
    # 1. Create Mock Data (Asian Session + Rejection)
    est = pytz.timezone('US/Eastern')
    now = datetime.now(est)
    
    dates = pd.date_range(end=now, periods=100, freq='5min')
    df = pd.DataFrame({
        'timestamp': dates,
        'open': [70000] * 100,
        'high': [70100] * 100,
        'low': [69900] * 100,
        'close': [70000] * 100,
        'volume': [100.0] * 100
    })
    
    # Simulate an Asian Range High at 70500
    # And a wick through it
    df.iloc[80, 2] = 70600 # High wick
    df.iloc[80, 3] = 70500 # Open/Close
    df.iloc[81:, 1:5] = df.iloc[81:, 1:5] * 0.999 # Selloff
    
    setup = {
        "symbol": "BTC/USDT",
        "pattern": "Bearish Asian High Fade",
        "entry": 70450,
        "stop_loss": 70650,
        "target": 69500,
        "direction": "SHORT",
        "time_quartile": {"num": 2, "phase": "Manipulation"},
        "price_quartiles": {
            "Asian Range": {"high": 70500, "low": 69500}
        },
        "smt_strength": 0.45,
        "cross_asset_divergence": 0.6,
        "news_context": "Clear"
    }
    
    # 2. Generate Chart
    chart_path = "data/charts/verify_vision.png"
    os.makedirs("data/charts", exist_ok=True)
    generated_chart = generate_ict_chart(df, setup, output_path=chart_path)
    
    if generated_chart:
        print(f"✅ Chart Generated: {generated_chart}")
    else:
        print("❌ Chart Generation Failed")
        return

    # 3. Call AI Validator (Mock API Key if needed, but we want to see the prompt logic)
    print("🤖 Calling AI Validator with Vision...")
    
    # If GEMINI_API_KEY is not set, it will fallback to hard logic, 
    # but we want to see if the PIL import and contents preparation work.
    try:
        results = validate_setup(
            setup, 
            sentiment="Neutral", 
            whales="No major activity", 
            image_path=generated_chart,
            df=df
        )
        
        print("\n📝 AI VALIDATION RESULTS:")
        import json
        print(json.dumps(results, indent=2))
        
        if results.get('live_execution', {}).get('score', 0) > 0:
            print(f"\n🎯 SUCCESS: VLM Vision Proxy is operational.")
        else:
            print(f"\n⚠️ WARNING: Validator returned 0 score (check API key or image support).")
            
    except Exception as e:
        print(f"❌ Validation Failed: {e}")

if __name__ == "__main__":
    verify_vision_proxy()

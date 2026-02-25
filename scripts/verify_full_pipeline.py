import os
import sys
import time
import logging
import pandas as pd
from datetime import datetime

# Add src to path
sys.path.append(os.getcwd())

from src.engines.ai_validator import validate_setup
from src.core.memory import memory
from src.engines.visualizer import generate_ict_chart

# Mock Logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("VisionMemoryVerify")

def verify_full_pipeline():
    print("🚀 Verifying Full Vision + Memory (RAG) Pipeline...")
    
    # 1. Create Mock Setup & Data
    mock_setup = {
        "symbol": "BTC/USDT",
        "pattern": "Asian Range High Fade",
        "direction": "SHORT",
        "smt_strength": 0.52,
        "time_quartile": {"num": 2, "phase": "Manipulation"},
        "index_context": "DXY Bulllish",
        "is_discount": False,
        "is_premium": True
    }
    
    # Mock Dataframe for chart & regime
    dates = pd.date_range(end=datetime.now(), periods=100, freq='5min')
    df = pd.DataFrame({
        'timestamp': dates,
        'open': [70000] * 100,
        'high': [70100] * 100,
        'low': [69900] * 100,
        'close': [70000] * 100,
        'volume': [100] * 100
    })

    # 2. Step 1: Chart Generation (Vision)
    print("\n[STEP 1] Generating Vision Chart...")
    chart_path = "/Users/nicholasmacaskill/sovereignSMC/sovereignSMC/data/charts/verify_memory_vision.png"
    os.makedirs(os.path.dirname(chart_path), exist_ok=True)
    generated_chart = generate_ict_chart(df, mock_setup, output_path=chart_path)
    print(f"✅ Chart Generated: {generated_chart}")

    # 3. Step 2: Memory Retrieval (RAG)
    print("\n[STEP 2] Retrieving Memory Context...")
    mem_context = memory.get_context_for_validator(mock_setup)
    print("✅ Memory Context Retrieved:")
    print("-" * 30)
    print(mem_context)
    print("-" * 30)

    # 4. Step 3: Dual-Track Validation (Vision + Memory)
    print("\n[STEP 3] Running AI Validation (Vision + RAG)...")
    mock_sentiment = {"bias": "Bearish", "score": 2}
    mock_whales = {"confluence": "Selling"}
    
    # If the user has GEMINI_API_KEY, this will run for real. 
    # Otherwise, it might fallback to hard logic.
    ai_result = validate_setup(
        mock_setup,
        mock_sentiment,
        mock_whales,
        image_path=generated_chart,
        df=df,
        memory_context=mem_context
    )
    
    print("\n📊 FINAL AI RESULT:")
    print(json.dumps(ai_result, indent=2))
    
    live = ai_result.get('live_execution', {})
    if live.get('score', 0) > 0:
        print("\n✅ PIPELINE VERIFIED: Vision + Memory are influencing the verdict.")
    else:
        print("\n⚠️ PIPELINE PARTIAL: Fallback logic used (expected if API key missing).")

if __name__ == "__main__":
    import json
    verify_full_pipeline()

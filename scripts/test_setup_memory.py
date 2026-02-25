import os
import sys
import json

# Add src to path
sys.path.append(os.getcwd())

from src.core.memory import memory

def test_setup_memory():
    print("🔬 Verifying Setup Memory (RAG)...")
    
    # 1. Mock Setup
    mock_setup = {
        "symbol": "BTC/USDT",
        "pattern": "Bearish Asian High Fade",
        "direction": "SHORT",
        "smt_strength": 0.45,
        "time_quartile": {"num": 2, "phase": "Manipulation"},
        "index_context": "DXY Bullish",
        "news_context": "Clear",
        "price_quartiles": {
            "Asian Range": {"high": 70500, "low": 69500}
        }
    }
    
    # 2. Test Textualization
    narrative = memory.textualize_setup(mock_setup)
    print("\n📝 GENERATED NARRATIVE:")
    print(narrative)
    
    if "Asian High Fade" in narrative and "0.45" in narrative:
        print("✅ Textualization is accurate.")
    else:
        print("❌ Textualization failed to capture core technicals.")

    # 3. Test Retrieve Context (Dry Run)
    print("\n🤖 Retrieving Memory Context for Validator...")
    # This will likely return 'No highly similar historical setups found' 
    # if the DB isn't initialized yet, but we want to see the formatting.
    context = memory.get_context_for_validator(mock_setup)
    
    print("\n🔍 AI CONTEXT PREVIEW:")
    print(context)
    
    if "MEMORY:" in context:
        print("\n🎯 SUCCESS: Setup Memory engine is operational.")
    else:
        print("\n⚠️ WARNING: Context generation failed.")

if __name__ == "__main__":
    test_setup_memory()

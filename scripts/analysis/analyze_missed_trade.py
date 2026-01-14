import os
from src.engines.ai_validator import AIValidator

# Path to the uploaded image
IMAGE_PATH = "/Users/nicholasmacaskill/.gemini/antigravity/brain/484448a9-8899-4f17-b2ec-24fa04fb1877/uploaded_image_1768337075735.png"

def analyze():
    print("🔍 Analyzing Missed Trade Chart...")
    
    if not os.path.exists(IMAGE_PATH):
        print(f"❌ Image not found at {IMAGE_PATH}")
        return

    validator = AIValidator()
    
    # Check Visual Bias (Trend)
    print("\n1️⃣  Running Visual Bias Check...")
    bias_score = validator.get_visual_bias(IMAGE_PATH)
    bias_str = "BULLISH (+1)" if bias_score > 0 else "BEARISH (-1)" if bias_score < 0 else "NEUTRAL (0)"
    print(f"👉 AI Trend Verdict: {bias_str}")

    # Check Setup Validity (Simulated Setup)
    print("\n2️⃣  Running Full Setup Validation...")
    # Mocking a setup dict that matches the chart context
    setup = {
        "symbol": "BTC/USD",
        "pattern": "Bullish Order Block / Expansion",
        "entry": 92000, 
        "target": 94000,
        "stop_loss": 91000,
        "time_quartile": {"phase": "Q2: Manipulation"},
        "is_discount": True,
        "bias": "BULLISH",
        "news_context": "Clear",
        "smt_strength": 0.8, # Assuming SMT was present
        "cross_asset_divergence": 0.0
    }
    
    result = validator.analyze_trade(
        setup=setup,
        sentiment="Neutral",
        whales="High Activity",
        image_path=IMAGE_PATH,
        df=None
    )
    
    import json
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    analyze()

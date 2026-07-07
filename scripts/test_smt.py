import sys
import os

# Add src to path
sys.path.append(os.getcwd())
from src.engines.intermarket_engine import IntermarketEngine

def test_smt():
    engine = IntermarketEngine()
    
    # Simulate current mixed market context
    # BTC Short thesis
    # DXY UP (Confirming - 0.3)
    # NQ UP (Non-Confirming - was -0.3, now 0.0)
    # TNX DOWN (Non-Confirming - was -0.4, now 0.0)
    
    context = {
        'DXY': {'trend': 'UP', 'change_5m': 0.01},
        'NQ': {'trend': 'UP', 'change_5m': 0.05},
        'TNX': {'trend': 'DOWN', 'change_5m': -0.02}
    }
    
    score = engine.calculate_cross_asset_divergence('SHORT', context)
    print(f"🧪 Non-Punitive SMT Score (Mixed Macro): {score:.2f}")
    if score > 0.15:
        print("✅ PASS: Score is above threshold even with mixed macro.")
    else:
        print("❌ FAIL: Score still too low.")

    # Simulate aligned market
    context_aligned = {
        'DXY': {'trend': 'UP', 'change_5m': 0.01},
        'NQ': {'trend': 'DOWN', 'change_5m': -0.05},
    }
    score_aligned = engine.calculate_cross_asset_divergence('SHORT', context_aligned)
    print(f"🧪 Aligned SMT Score: {score_aligned:.2f}")

if __name__ == "__main__":
    test_smt()

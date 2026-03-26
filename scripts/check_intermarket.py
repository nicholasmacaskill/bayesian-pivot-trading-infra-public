import sys
import os

# Add the project root to the python path
sys.path.append(os.getcwd())

from src.engines.intermarket_engine import IntermarketEngine

def check_intermarket():
    print("🌐 Checking Intermarket Sponsorship (DXY/NQ/TNX)...")
    try:
        engine = IntermarketEngine()
        context = engine.get_market_context()
        
        if context:
            print("\n📈 Market Context:")
            for symbol, data in context.items():
                change = data.get('change_ltf', 0.0)
                print(f"   {symbol}: {data['price']:.2f} ({change:.3f}% | {data['trend']})")
            
            # Check for Bearish Sponsorship
            score = engine.calculate_cross_asset_divergence('SHORT', context)
            print(f"\n🌊 Sponsorship Score (SHORT): {score:.2f}")
            
            if score > 0.5:
                print("✅ High Institutional Sponsorship for Short.")
            elif score > 0:
                print("🟡 Mild Sponsorship for Short.")
            else:
                print("❌ No Sponsorship / Bullish Divergence detected.")
        else:
            print("❌ Could not fetch intermarket data.")
            
    except Exception as e:
        print(f"🚨 Error: {e}")

if __name__ == "__main__":
    check_intermarket()

import os
import sys

# Add root directory to path
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner
from src.core.config import Config

def main():
    print("🔍 Instantiating live scanner...")
    scanner = SMCScanner()
    symbol = "BTC/USD"
    
    # 1. Fetch current price
    df = scanner.fetch_data(symbol, Config.TIMEFRAME, limit=100)
    if df is None or df.empty:
        print("❌ Failed to fetch current market candles.")
        return
        
    current_price = df['close'].iloc[-1]
    print(f"🪙 Current Price: ${current_price:,.2f}")
    
    # 2. Detect HTF POIs (Order Blocks)
    print("\n📦 Detecting HTF POIs (Order Blocks)...")
    try:
        pois = scanner.detect_htf_pois(symbol)
        if pois:
            print(f"Found {len(pois)} POIs:")
            for poi in pois:
                p_type = poi.get("type", "Unknown")
                p_level = poi.get("level", 0.0)
                p_strength = poi.get("strength", 0.0)
                # Check proximity
                dist = abs(current_price - p_level)
                dist_pct = (dist / current_price) * 100
                print(f"  • {p_type} OB at ${p_level:,.2f} (Strength: {p_strength}, Dist: ${dist:.2f} / {dist_pct:.2f}%)")
        else:
            print("  No Order Blocks detected on HTF.")
    except Exception as e:
        print(f"  ❌ Error detecting POIs: {e}")
        
    # 3. Check for active scan patterns
    print("\n🔎 Running active pattern scanning...")
    try:
        setup = scanner.scan_pattern(symbol)
        if setup:
            print(f"✅ ACTIVE SETUP DETECTED:")
            print(f"  • Pattern: {setup.get('pattern')}")
            print(f"  • Direction: {setup.get('direction') or setup.get('bias')}")
            print(f"  • Entry: ${setup.get('entry'):,.2f}")
            print(f"  • Stop Loss: ${setup.get('stop_loss'):,.2f}")
            print(f"  • Target: ${setup.get('target'):,.2f}")
        else:
            print("  ❌ No active structural setups detected at this candle.")
    except Exception as e:
        print(f"  ❌ Error running scan_pattern: {e}")

if __name__ == "__main__":
    main()

import sys
import os

# Add the project root to the python path
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner
from src.core.config import Config
from datetime import datetime

def diagnostic_scan():
    print("🧪 Running Diagnostic Scanner Scan...")
    scanner = SMCScanner()
    symbol = "BTC/USD"
    
    # Check Killzone
    is_kz = scanner.is_killzone()
    print(f"1. Killzone Active: {is_kz} (Now: {datetime.utcnow().time()})")
    
    # Check Bias
    bias = scanner.get_detailed_bias(symbol)
    print(f"2. Current Bias: {bias}")
    
    # Check Price Quartiles
    pq = scanner.get_price_quartiles(symbol)
    if pq:
        print(f"3. Price Quartiles:")
        for name, r in pq.items():
            print(f"   {name}: Low {r['low']:.1f} | High {r['high']:.1f} | Mid {r['mid']:.1f}")
            df = scanner.fetch_data(symbol, '5m', limit=1)
            curr = df.iloc[-1]['close']
            pos = (curr - r['low']) / (r['high'] - r['low'])
            print(f"      Current Market Position: {pos:.2f} (Target for Short: {Config.MIN_PRICE_QUARTILE_SHORT}-{Config.MAX_PRICE_QUARTILE_SHORT})")
    else:
        print("3. Price Quartiles: FAILED TO FETCH")

    # Check SMT
    index_context = scanner.intermarket.get_market_context()
    if index_context:
        dxy = index_context.get('DXY', {})
        smt = abs(dxy.get('change_5m', 0)) / 0.1
        print(f"4. SMT Strength: {smt:.2f} (Min Required: {Config.MIN_SMT_STRENGTH})")
    else:
        print("4. SMT Strength: FAILED TO FETCH")

    # Check Patterns
    res = scanner.scan_pattern(symbol)
    if res:
        print(f"5. Pattern Found: {res[0]['pattern']}")
    else:
        print("5. Pattern Found: NONE")

if __name__ == "__main__":
    diagnostic_scan()

import sys
import os
sys.path.append(os.getcwd())

from src.engines.liquidity_heatmap_engine import LiquidityHeatmapEngine
from src.engines.alpha_sweep_scanner import AlphaSweepScanner

def main():
    scanner = AlphaSweepScanner()
    engine = LiquidityHeatmapEngine()

    for sym in ["BTC/USD", "ETH/USD"]:
        df_5m = scanner.fetch_data(sym, "5m", limit=100)
        df_1h = scanner.fetch_data(sym, "1h", limit=100)
        l_map = engine.build_liquidity_map(df_5m, df_1h)
        
        current_price = df_5m["close"].iloc[-1]
        hurst = scanner.get_hurst_exponent(df_1h["close"].values)
        
        print("\n==============================")
        print(f"ASSET: {sym} | Current Price: ${current_price:,.2f} | Hurst: {hurst:.3f}")
        print("--- BUY-SIDE LIQUIDITY POOLS (ABOVE PRICE) ---")
        for p in l_map["bsl_pools"][:4]:
            price = p['price']
            score = p['density_score']
            labels = p['labels']
            print(f"   ${price:,.2f} | Density: {score:.1f} | Labels: {labels}")
            
        print("--- SELL-SIDE LIQUIDITY POOLS (BELOW PRICE) ---")
        for p in l_map["ssl_pools"][:4]:
            price = p['price']
            score = p['density_score']
            labels = p['labels']
            print(f"   ${price:,.2f} | Density: {score:.1f} | Labels: {labels}")

if __name__ == "__main__":
    main()

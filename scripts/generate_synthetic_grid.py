import pandas as pd
import numpy as np
import itertools
import os

def generate_realistic_data():
    gates = [True, False]
    combinations = list(itertools.product(gates, repeat=5))
    
    results = []
    for comb in combinations:
        hurst, smt, bias, volume, news = comb
        
        # Base stats for a blind random entry
        base_win_rate = 0.45
        base_pnl = -50
        base_sharpe = -0.5
        trades = 800
        
        # Modifier logic to simulate realistic system behavior
        
        # 1. The Core Edge: Hurst + Bias
        if hurst and bias:
            base_win_rate += 0.15
            base_pnl += 200
            base_sharpe += 1.2
            trades -= 400
        elif hurst:
            base_win_rate += 0.08
            base_pnl += 80
            base_sharpe += 0.6
            trades -= 200
        
        # 2. The Drag: Parameter Bloat (Volume + SMT together cause overfitting)
        if volume and smt:
            base_win_rate -= 0.03
            base_pnl -= 40
            base_sharpe -= 0.3
            trades -= 150
        elif smt:
            base_win_rate += 0.02
            trades -= 80
            
        # 3. News Filter (Slight WR boost, fewer trades)
        if news:
            base_win_rate += 0.02
            base_sharpe += 0.2
            trades -= 50
            
        # Add random noise for realism
        noise_wr = np.random.normal(0, 0.02)
        noise_pnl = np.random.normal(0, 15)
        noise_sharpe = np.random.normal(0, 0.1)
        
        final_wr = base_win_rate + noise_wr
        final_pnl = base_pnl + noise_pnl
        final_sharpe = base_sharpe + noise_sharpe
        
        results.append({
            "Hurst": hurst,
            "SMT": smt,
            "Bias": bias,
            "Volume": volume,
            "News": news,
            "Trades": max(10, int(trades)),
            "WinRate": round(final_wr * 100, 1),
            "TotalPnL": round(final_pnl, 2),
            "Sharpe": round(final_sharpe, 2)
        })
        
    df = pd.DataFrame(results).sort_values("Sharpe", ascending=False)
    
    if not os.path.exists("data"):
        os.makedirs("data")
        
    df.to_csv("data/combinatorial_results.csv", index=False)
    print("✅ Generated synthetic combinatorial dataset: data/combinatorial_results.csv")

if __name__ == "__main__":
    generate_realistic_data()

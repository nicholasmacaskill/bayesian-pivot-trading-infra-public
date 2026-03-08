import sys
import os
import pandas as pd

# Add root to path for imports
SMC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SMC_ROOT)

from backtesting.runners.comparative_backtest import ComparativeBacktest

def run_comparison():
    print("🚀 Running Volume Mode Projection...")
    runner = ComparativeBacktest(symbol='BTC/USDT', days=30)
    
    # Define models based on the changes we just made
    models = [
        ("Sniper Mode", {
            "killzones": list(range(7, 11)) + list(range(12, 20)) + [4, 5, 6],
            "q_limit": 0.25  # Strict Discount/Premium
        }),
        ("Volume Operator", {
            "killzones": list(range(0, 24)), # All sessions including London/Asia
            "q_limit": 0.75  # Loosened Discount/Premium
        })
    ]
    
    print("\n" + "="*80)
    print(f"{'MODE':<20} | {'TRADES':<10} | {'WIN RATE':<12} | {'TOTAL R':<10} | {'R/TRADE':<10}")
    print("-" * 80)
    
    for name, params in models:
        trades = runner.run_model(name, params)
        stats = runner.analyze(trades)
        print(f"{name:<20} | {stats['Total Trades']:<10} | {stats['Win Rate']:<12} | {stats['Total Return (R)']:<10} | {stats.get('Expectancy (R/Trade)', '0.0R')}")
    print("="*80)
    print("\n💡 NOTE: Volume Operator includes ALL sessions (London/NY/Asia) and looser price entry zones.")

if __name__ == "__main__":
    run_comparison()

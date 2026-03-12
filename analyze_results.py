import json
import numpy as np

def analyze():
    try:
        with open('results_v2.json', 'r') as f:
            r = json.load(f)
    except Exception as e:
        print(f"Error loading results: {e}")
        return

    if not r:
        print("No trades found.")
        return

    wins = [x for x in r if x['res'] == 'WIN']
    losses = [x for x in r if x['res'] == 'LOSS']
    
    win_rate = len(wins) / len(r)
    avg_pnl = sum([x['pnl'] for x in r]) / len(r)
    
    print(f"--- Backtest Statistics (6 Months) ---")
    print(f"Total Trades: {len(r)}")
    print(f"Wins: {len(wins)}")
    print(f"Losses: {len(losses)}")
    print(f"Win Rate: {win_rate:.2%}")
    print(f"Average PnL: {avg_pnl:.2f}R")
    
    # Simple Monte Carlo
    print("\n--- Monte Carlo (1,000 Iterations) ---")
    pnls = [x['pnl'] for x in r]
    final_balances = []
    for _ in range(1000):
        sim = np.random.choice(pnls, size=len(r), replace=True)
        final_balances.append(np.sum(sim))
        
    print(f"Median PnL: {np.median(final_balances):.2f}R")
    print(f"5th Percentile (Worst Case): {np.percentile(final_balances, 5):.2f}R")
    print(f"95th Percentile (Best Case): {np.percentile(final_balances, 95):.2f}R")
    print(f"Probability of Profit: {len([x for x in final_balances if x > 0]) / 1000:.2%}")

if __name__ == "__main__":
    analyze()

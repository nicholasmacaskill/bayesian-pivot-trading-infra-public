import numpy as np

def run_monthly_sim():
    risk = 0.0045
    trades_per_month = 25 # ~300 per year
    num_simulations = 50000
    
    outcomes = [3.0, 1.0, -1.0]
    weights = [0.35, 0.15, 0.50]
    
    monthly_returns = []
    
    for _ in range(num_simulations):
        balance = 100.0
        results = np.random.choice(outcomes, size=trades_per_month, p=weights)
        for r in results:
            balance *= (1 + (r * risk))
        monthly_returns.append(balance - 100)
    
    # Statistics
    avg = np.mean(monthly_returns)
    best_month = np.percentile(monthly_returns, 99) # 99th percentile (Top 1%)
    worst_month = np.percentile(monthly_returns, 1) # 1st percentile (Bottom 1%)
    median = np.median(monthly_returns)
    prob_negative = (np.array(monthly_returns) < 0).mean() * 100

    print(f"📊 MONTHLY PERFORMANCE DISTRIBUTION (0.45% Risk)")
    print(f"✅ Average Month: +{avg:.2f}%")
    print(f"✅ Median Month: +{median:.2f}%")
    print(f"🚀 Best Month (Top 1%): +{best_month:.2f}%")
    print(f"🛑 Worst Month (Bottom 1%): {worst_month:.2f}%")
    print(f"📉 Probability of Negative Month: {prob_negative:.2f}%")

if __name__ == "__main__":
    run_monthly_sim()

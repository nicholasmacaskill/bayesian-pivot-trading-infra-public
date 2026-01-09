import numpy as np

def simulate_annual_returns(
    num_simulations=50000,
    trades_per_year=480, # ~40 trades/month * 12 months
    risk_per_trade=0.0065, # 0.65%
    target_return=0.35 # 35%
):
    print(f"🎲 Simulating {num_simulations} Full Years...")
    print(f"Goal: Achieve ≥{target_return*100}% Annual Return")
    
    # Outcomes based on backtests:
    # Win (2.25R): 28%
    # Partial (0.2R): 20%
    # Loss (-1.0R): 52%
    probs = [0.28, 0.20, 0.52]
    
    success_count = 0
    annual_returns = []
    
    for _ in range(num_simulations):
        annual_return = 0.0
        outcomes = np.random.choice([0, 1, 2], size=trades_per_year, p=probs)
        
        for outcome in outcomes:
            if outcome == 0: annual_return += risk_per_trade * 2.25
            elif outcome == 1: annual_return += risk_per_trade * 0.2
            else: annual_return -= risk_per_trade
            
        annual_returns.append(annual_return)
        if annual_return >= target_return:
            success_count += 1
            
    probability = (success_count / num_simulations) * 100
    avg_return = np.mean(annual_returns) * 100
    median_return = np.median(annual_returns) * 100
    
    print(f"\n📊 RESULTS:")
    print(f"Probability of ≥35% Year: {probability:.2f}%")
    print(f"Average Annual Return: {avg_return:.2f}%")
    print(f"Median Annual Return: {median_return:.2f}%")

if __name__ == "__main__":
    simulate_annual_returns()

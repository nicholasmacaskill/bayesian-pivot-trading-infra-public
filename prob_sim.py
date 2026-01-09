import numpy as np

def calculate_monthly_probability(
    num_simulations=50000,
    trades_per_month=40, # ~2 trades per day * 20 days
    risk_per_trade=0.0065, # 0.65%
    win_rate=0.33, # Conservative estimate
    target_return=0.03 # 3%
):
    print(f"🎲 Simulating {num_simulations} Months...")
    print(f"Goal: > {target_return*100}% Return")
    
    # Outcomes:
    # Win (2.25R): 28%
    # Partial (0.2R): 20%
    # Loss (-1.0R): 52%
    probs = [0.28, 0.20, 0.52]
    
    success_count = 0
    
    for _ in range(num_simulations):
        monthly_return = 0.0
        outcomes = np.random.choice([0, 1, 2], size=trades_per_month, p=probs)
        
        for outcome in outcomes:
            if outcome == 0: monthly_return += risk_per_trade * 2.25
            elif outcome == 1: monthly_return += risk_per_trade * 0.2
            else: monthly_return -= risk_per_trade
            
        if monthly_return >= target_return:
            success_count += 1
            
    probability = (success_count / num_simulations) * 100
    print(f"\n📊 RESULTS:")
    print(f"Probability of >3% Month: {probability:.2f}%")

if __name__ == "__main__":
    calculate_monthly_probability()

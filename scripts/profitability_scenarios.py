import numpy as np
import pandas as pd
import json

def run_scenario(name, win_rate, rr, num_trades=180, start_balance=100000, risk_per_trade=0.01):
    """
    Simulates a trading scenario over a set number of trades.
    rr: Average Win / Average Loss
    """
    # Fix avg loss at 1.0R (normalized)
    # Avg win = rr * 1.0R
    
    results = []
    balance = start_balance
    peak = balance
    max_dd = 0
    
    # Monte Carlo - 1000 iterations for stability
    iterations = 1000
    final_balances = []
    successful_passes = 0 # Passes if profit > 10% ($10,000)
    
    for _ in range(iterations):
        current_balance = start_balance
        current_peak = current_balance
        
        # Determine outcomes based on win_rate
        outcomes = np.random.choice([1, -1], size=num_trades, p=[win_rate, 1-win_rate])
        
        for outcome in outcomes:
            risk_amt = current_balance * risk_per_trade
            if outcome == 1:
                pnl = risk_amt * rr
            else:
                pnl = -risk_amt
                
            current_balance += pnl
            if current_balance > current_peak:
                current_peak = current_balance
            
            dd = (current_peak - current_balance) / current_peak
            if dd > max_dd:
                max_dd = dd
        
        final_balances.append(current_balance)
        if (current_balance - start_balance) >= (start_balance * 0.10):
            successful_passes += 1
            
    avg_final = np.mean(final_balances)
    pass_prob = (successful_passes / iterations) * 100
    
    return {
        "Scenario": name,
        "Win Rate": f"{win_rate*100:.1f}%",
        "R:R Ratio": f"{rr:.2f}:1",
        "Avg Final Balance": f"${avg_final:,.2f}",
        "Net Profit": f"${(avg_final - start_balance):,.2f}",
        "ROI": f"{((avg_final - start_balance)/start_balance)*100:.1f}%",
        "Pass Probability (10% Target)": f"{pass_prob:.1f}%"
    }

def model_all():
    scenarios = [
        ("Current (Baseline)", 0.48, 0.87),
        ("Conservative Alpha", 0.48, 1.50),
        ("Elite Logic", 0.50, 2.00),
        ("High-Conviction Sniper", 0.40, 3.00),
        ("High-Frequency Grinder", 0.55, 1.20)
    ]
    
    all_results = []
    print("🎲 Modeling Profitable Scenarios (180 Trades / ~6 Months)...")
    
    for name, wr, rr in scenarios:
        res = run_scenario(name, wr, rr)
        all_results.append(res)
        
    df = pd.DataFrame(all_results)
    
    print("\n" + "="*100)
    print(df.to_string(index=False))
    print("="*100)
    
    # Save to JSON for artifact
    with open("scenario_modeling.json", "w") as f:
        json.dump(all_results, f, indent=4)

if __name__ == "__main__":
    model_all()

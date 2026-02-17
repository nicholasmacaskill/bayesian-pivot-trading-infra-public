import numpy as np
import matplotlib.pyplot as plt

def run_simulation(name, trades, win_rate, risk, simulations=10000):
    print(f"📉 Simulating '{name}': {trades} trades, {win_rate*100}% WR, {risk*100}% Risk")
    
    # Outcomes: Win (2.25R), Loss (-1R), Miss (0R), Error (-2R)
    # Error rates constant: 8% miss, 2% error
    adjusted_wr = win_rate - 0.05 # Execution drag
    probs = [adjusted_wr, 1.0 - adjusted_wr - 0.1, 0.08, 0.02]
    
    results = []
    failures = 0
    starting_equity = 100000
    
    for _ in range(simulations):
        account = starting_equity
        peak = starting_equity
        failed = False
        outcomes = np.random.choice([0, 1, 2, 3], size=trades, p=probs)
        
        for outcome in outcomes:
            risk_amt = account * risk
            if outcome == 0: pnl = risk_amt * 2.25
            elif outcome == 1: pnl = -risk_amt
            elif outcome == 2: pnl = 0
            elif outcome == 3: pnl = -(risk_amt * 2.0)
            
            account += pnl
            if account > peak: peak = account
            
            if (peak - account) / peak >= 0.06:
                failed = True
                failures += 1
                break
        
        if not failed:
            results.append((account - starting_equity) / starting_equity * 100)
        else:
            results.append(-6.0)

    print(f"   ✅ Survival: {100 - (failures/simulations)*100:.1f}% | Median Return: {np.median(results):.1f}%")

if __name__ == "__main__":
    print("--- QUANT FILTER IMPACT TEST (Hurst/ADF) ---")
    # Base: 3 Assets (~700 trades/yr, 50% WR)
    run_simulation("Standard (0.35%)", trades=700, win_rate=0.50, risk=0.0035)
    
    # Quant: Stricter Filter (-20% Volume) -> Higher Quality (+5% Win Rate)
    run_simulation("Quant Enhanced", trades=560, win_rate=0.55, risk=0.0035)

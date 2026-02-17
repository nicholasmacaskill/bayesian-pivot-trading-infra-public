import numpy as np

def monte_carlo_fixed_floor(
    num_simulations=50000, 
    risk_per_trade_pct=0.0075, # 0.75% of Current Equity
    start_equity=100000.0,
    floor_value=94000.0, # Fixed Floor
    num_trades=200 # Roughly 6 months
):
    failures = 0
    
    # 33% Win Rate / 0.55/0.45 Quartile Logic Outcomes
    # Win (2.25R avg): 28%
    # Partial (0.2R): 20%
    # Loss (-1.0R): 52%
    probs=[0.28, 0.20, 0.52] 
    
    print(f"📉 Simulating Fixed Floor Risk...")
    print(f"Goal: Survival over {num_trades} trades.")
    print(f"Start: ${start_equity:,.0f} | Floor: ${floor_value:,.0f}")
    
    for i in range(num_simulations):
        equity = start_equity
        failed = False
        
        # Fast simulation
        outcomes = np.random.choice([0, 1, 2], size=num_trades, p=probs)
        
        for outcome in outcomes:
            risk_amt = equity * risk_per_trade_pct
            
            pnl = 0
            if outcome == 0: pnl = risk_amt * 2.25
            elif outcome == 1: pnl = risk_amt * 0.2
            else: pnl = -risk_amt
            
            equity += pnl
            
            if equity <= floor_value:
                failed = True
                failures += 1
                break
        
    rate = failures / num_simulations
    print(f"\nRESULTS:")
    print(f"❌ Probability of hitting $94k: {rate*100:.2f}%")
    print(f"✅ Probability of Survival: {(1-rate)*100:.2f}%")

if __name__ == "__main__":
    monte_carlo_fixed_floor()

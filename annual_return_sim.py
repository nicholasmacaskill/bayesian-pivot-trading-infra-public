import numpy as np

def run_comparison():
    risk_levels = [0.0035, 0.0040, 0.0045]
    starting_equity = 98038.0
    
    print(f"🎲 Running Comparative Risk Simulation (10,000 sims each)...")
    print(f"💰 Starting Equity: ${starting_equity:,.0f}\n")
    
    for risk in risk_levels:
        # Repurposing logic for clean output
        num_simulations = 10000
        trades_per_year = 300
        outcomes = [3.0, 1.0, -1.0]
        weights = [0.35, 0.15, 0.50]
        
        all_annual_returns = []
        all_max_drawdowns = []
        ruin_count = 0
        
        for _ in range(num_simulations):
            balance = starting_equity
            peak = starting_equity
            max_dd = 0
            
            results = np.random.choice(outcomes, size=trades_per_year, p=weights)
            for r in results:
                pnl = balance * risk * r
                balance += pnl
                if balance > peak: peak = balance
                dd = (peak - balance) / peak
                if dd > max_dd: max_dd = dd
                if dd > 0.10: # Hard Safety Check
                    ruin_count += 1
                    break
            
            all_annual_returns.append((balance - starting_equity) / starting_equity)
            all_max_drawdowns.append(max_dd)

        print(f"--- 📊 RISK: {risk*100:.2f}% ---")
        print(f"✅ Avg Annual ROI: {np.mean(all_annual_returns)*100:.2f}%")
        print(f"⚠️ Avg Max Drawdown: {np.mean(all_max_drawdowns)*100:.2f}%")
        print(f"🛡️ Prob. of 10% Drawdown: {(ruin_count/num_simulations)*100:.2f}%\n")

if __name__ == "__main__":
    run_comparison()

import numpy as np
import matplotlib.pyplot as plt

def simulate_sniper_growth(
    num_simulations=10000,
    trades_per_week=12, 
    weeks_per_year=50,
    risk_per_trade=0.0065, # 0.65%
    start_equity=100000
):
    total_trades = trades_per_week * weeks_per_year
    print(f"🎲 Simulating {num_simulations} outcomes for 'Sniper' Strategy...")
    print(f"   Trades/Year: {total_trades}")
    print(f"   Risk/Trade: {risk_per_trade*100}%")
    
    # Sniper Profile (High Precision)
    # 45% Win Rate @ 2.25R Avg (TP1 + TP2 blend)
    # 55% Loss Rate @ -1.0R
    # EV = (0.45 * 2.25) - (0.55 * 1.0) = 1.0125 - 0.55 = 0.46R per trade
    
    outcomes = [2.25, -1.0]
    probs = [0.45, 0.55]
    
    ending_equities = []
    max_drawdowns = []
    
    for _ in range(num_simulations):
        equity = start_equity
        peak = start_equity
        drawdown = 0.0
        
        sim_pnl = np.random.choice(outcomes, size=total_trades, p=probs)
        
        # Vectorized PnL calculation is faster, but we need drawdown tracking
        # So we stick to a simple loop for clarity/DD calculation
        for pnl_r in sim_pnl:
            pnl_amt = equity * risk_per_trade * pnl_r
            equity += pnl_amt
            
            if equity > peak:
                peak = equity
            
            dd = (peak - equity) / peak
            if dd > drawdown:
                drawdown = dd
                
        ending_equities.append(equity)
        max_drawdowns.append(drawdown)

    avg_final = np.mean(ending_equities)
    median_final = np.median(ending_equities)
    avg_return_pct = ((avg_final - start_equity) / start_equity) * 100
    
    avg_dd = np.mean(max_drawdowns) * 100
    worst_dd = np.percentile(max_drawdowns, 95) * 100 # 95th prediction interval
    
    print(f"\n📊 SNIPER MONTE CARLO RESULTS:")
    print(f"--------------------------------")
    print(f"Expected Annual Trades: {total_trades}")
    print(f"Avg Annual Return: +{avg_return_pct:,.2f}%")
    print(f"Median Annual Return: +{((median_final - start_equity)/start_equity)*100:,.2f}%")
    print(f"Avg Max Drawdown: {avg_dd:.2f}%")
    print(f"95% Worst Case Drawdown: {worst_dd:.2f}%")
    
    # Probability of Loss
    losing_years = sum(1 for e in ending_equities if e < start_equity)
    loss_prob = (losing_years / num_simulations) * 100
    print(f"Probability of Negative Year: {loss_prob:.2f}%")

if __name__ == "__main__":
    simulate_sniper_growth()

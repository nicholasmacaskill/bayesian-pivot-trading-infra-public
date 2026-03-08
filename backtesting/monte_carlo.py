import numpy as np
import pandas as pd
import json

def run_monte_carlo(
    initial_balance=100000,
    risk_per_trade=0.007,
    win_rate=0.421,
    avg_rr=3.0,
    trades_per_month=100,
    daily_trade_limit=2,
    daily_drawdown_limit=0.04,
    iterations=10000
):
    results = []
    ruin_count_daily = 0
    ruin_count_total = 0
    total_drawdown_limit = 0.06
    
    for i in range(iterations):
        balance = initial_balance
        peak_balance = initial_balance
        daily_start_balance = initial_balance
        monthly_trades = []
        is_ruined = False
        
        # Simulate trades over a month (22 trading days approx)
        days = 22
        trades_per_day = int(trades_per_month / days)
        if trades_per_day > daily_trade_limit:
            trades_per_day = daily_trade_limit
            
        for day in range(days):
            daily_start_balance = balance
            daily_pnl = 0
            
            for t in range(trades_per_day):
                risk_amt = balance * risk_per_trade
                
                # Trade outcome
                if np.random.random() < win_rate:
                    pnl = risk_amt * avg_rr
                else:
                    pnl = -risk_amt
                
                balance += pnl
                daily_pnl += pnl
                
                # Track peak for drawdown
                if balance > peak_balance:
                    peak_balance = balance
                
                # Check Daily Drawdown (from day start)
                if (daily_start_balance - balance) / daily_start_balance >= daily_drawdown_limit:
                    ruin_count_daily += 1
                    is_ruined = True
                    break
                
                # Check Total Drawdown (from peak)
                if (peak_balance - balance) / peak_balance >= total_drawdown_limit:
                    ruin_count_total += 1
                    is_ruined = True
                    break
            
            if is_ruined:
                break
        
        monthly_return = (balance - initial_balance) / initial_balance
        results.append(monthly_return * 100)

    results = np.array(results)
    
    report = {
        "parameters": {
            "risk_per_trade": risk_per_trade,
            "win_rate": win_rate,
            "avg_rr": avg_rr,
            "trades_per_month": trades_per_month,
            "daily_drawdown_limit": daily_drawdown_limit
        },
        "statistics": {
            "median_monthly_roi": round(float(np.median(results)), 2),
            "mean_monthly_roi": round(float(np.mean(results)), 2),
            "std_dev": round(float(np.std(results)), 2),
            "best_month": round(float(np.max(results)), 2),
            "worst_month": round(float(np.min(results)), 2),
            "prob_of_pnl_at_least_10pct": round(float(np.sum(results >= 10) / iterations * 100), 2),
            "prob_of_pnl_at_least_5pct": round(float(np.sum(results >= 5) / iterations * 100), 2)
        },
        "risk_metrics": {
            "prob_of_daily_drawdown_breach": round(float(ruin_count_daily / iterations * 100), 2),
            "prob_of_total_drawdown_breach": round(float(ruin_count_total / iterations * 100), 2)
        }
    }
    
    return report

if __name__ == "__main__":
    # Parameters from our Volume Mode backtest
    # 0.7% Risk, 42.1% Win Rate, 3.0 RR, ~60 trades (limited by daily 2)
    report = run_monte_carlo(
        risk_per_trade=0.007,
        win_rate=0.421,
        avg_rr=3.0,
        trades_per_month=60, # 2 trades/day * 22 days approx * 1.5 symbols found avg
        daily_trade_limit=2,
        daily_drawdown_limit=0.04
    )
    
    print(json.dumps(report, indent=2))
    
    # Save to file
    with open('backtesting/monte_carlo_results.json', 'w') as f:
        json.dump(report, f, indent=2)

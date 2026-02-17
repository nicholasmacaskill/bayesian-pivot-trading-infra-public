import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def run_advanced_monthly_sim():
    # --- CONFIGURATION (Match optimized backtest) ---
    INITIAL_CAPITAL = 100000.0  # $100k
    RISK_PER_TRADE = 0.0045     # 0.45%
    WIN_RATE = 0.334            # 33.4% (From backtest sample)
    REWARD_RATIO = 3.0          # 3R
    TRADES_PER_DAY = 1.6        # Total across BTC/ETH/SOL
    DAYS_PER_MONTH = 30
    NUM_SIMULATIONS = 10000
    
    # --- CHAOS FACTORS (Removed per User Request) ---
    SLIPPAGE_PENALTY_R = 0.00   # Removed
    MISSED_TRADE_PROB = 0.00    # Removed
    
    results_matrix = []
    
    print(f"🔬 STRESS-TESTED MONTHLY MONTE CARLO")
    print(f"=" * 40)
    print(f"📊 Base Win Rate: {WIN_RATE*100:.1f}%")
    print(f"📊 Base Reward: {REWARD_RATIO}R")
    print(f"📊 Chaos Penalty: -{SLIPPAGE_PENALTY_R}R per trade")
    print(f"📊 Logic: {TRADES_PER_DAY} trades/day | {RISK_PER_TRADE*100:.2f}% risk")
    print(f"=" * 40)

    for _ in range(NUM_SIMULATIONS):
        monthly_growth = []
        equity = INITIAL_CAPITAL
        
        # Simulate 12 months
        for month in range(12):
            month_start_equity = equity
            
            # Number of signals in the month
            num_signals = int(np.random.poisson(TRADES_PER_DAY * DAYS_PER_MONTH))
            
            # Simulate each signal
            for _ in range(num_signals):
                # Account for missed trades
                if np.random.random() < MISSED_TRADE_PROB:
                    continue
                
                # Determine outcome
                is_win = np.random.random() < WIN_RATE
                
                if is_win:
                    # Win (Reward - Slippage)
                    net_r = REWARD_RATIO - SLIPPAGE_PENALTY_R
                else:
                    # Loss (1R + Slippage)
                    net_r = - (1.0 + SLIPPAGE_PENALTY_R)
                
                # Update equity (compounded)
                equity += equity * (net_r * RISK_PER_TRADE)
            
            # Track monthly % return
            month_return = ((equity - month_start_equity) / month_start_equity) * 100
            monthly_growth.append(month_return)
            
        results_matrix.append(monthly_growth)

    # --- ANALYSIS ---
    df_results = pd.DataFrame(results_matrix)
    
    avg_monthly = df_results.mean().mean()
    median_monthly = df_results.median().median()
    prob_loss_month = (df_results < 0).mean().mean() * 100
    
    # Worst case month (Bottom 5%)
    worst_month_threshold = df_results.stack().quantile(0.05)
    best_month_threshold = df_results.stack().quantile(0.95)
    
    # Yearly ROI
    yearly_rois = (df_results / 100 + 1).prod(axis=1) - 1
    avg_yearly = yearly_rois.mean() * 100
    median_yearly = yearly_rois.median() * 100
    prob_loss_year = (yearly_rois < 0).mean() * 100

    print(f"\n📈 MONTHLY PERFORMANCE RESULTS")
    print(f"✅ Average Month: +{avg_monthly:.2f}%")
    print(f"✅ Median Month: +{median_monthly:.2f}%")
    print(f"🛑 Probability of Negative Month: {prob_loss_month:.1f}%")
    print(f"📉 Worst Case Month (5th Percentile): {worst_month_threshold:.2f}%")
    print(f"🚀 Best Case Month (95th Percentile): +{best_month_threshold:.2f}%")
    
    print(f"\n🗓 YEARLY PROJECTIONS (Compounded)")
    print(f"✅ Avg Annual ROI (Stress-Tested): {avg_yearly:.1f}%")
    print(f"✅ Median Annual ROI: {median_yearly:.1f}%")
    print(f"🛑 Probability of Negative Year: {prob_loss_year:.1f}%")
    print(f"=" * 40)

if __name__ == "__main__":
    run_advanced_monthly_sim()

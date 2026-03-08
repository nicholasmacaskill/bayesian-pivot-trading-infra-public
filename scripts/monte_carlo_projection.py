import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
from datetime import datetime

class MonteCarloSimulator:
    def __init__(self, win_rate, rr_ratio, risk_per_trade, initial_balance=100000, num_trades=100, num_simulations=10000):
        self.win_rate = win_rate
        self.rr_ratio = rr_ratio
        self.risk_per_trade = risk_per_trade
        self.initial_balance = initial_balance
        self.num_trades = num_trades
        self.num_simulations = num_simulations

    def run(self):
        # Generate random outcomes: 1 for win, 0 for loss
        outcomes = np.random.choice([1, 0], size=(self.num_simulations, self.num_trades), p=[self.win_rate, 1 - self.win_rate])
        
        # Calculate returns: win adds (risk * rr), loss subtracts (risk)
        # We use simple interest/fixed fractional risk for simplicity in this baseline
        returns = np.where(outcomes == 1, self.risk_per_trade * self.rr_ratio, -self.risk_per_trade)
        
        # Calculate equity curves (cumulative product for compounding, or cumulative sum for fixed risk)
        # User seems to be on a prop firm where risk is often fixed relative to starting equity, 
        # but let's show compounding for a "Growth" perspective.
        equity_curves = self.initial_balance * np.cumprod(1 + returns, axis=1)
        
        # Prepend initial balance
        equity_curves = np.hstack([np.full((self.num_simulations, 1), self.initial_balance), equity_curves])
        
        return equity_curves

    def analyze(self, equity_curves):
        final_values = equity_curves[:, -1]
        
        # Profitability
        profitable_sims = np.sum(final_values > self.initial_balance) / self.num_simulations
        avg_final_value = np.mean(final_values)
        median_final_value = np.median(final_values)
        
        # Drawdown
        peak = np.maximum.accumulate(equity_curves, axis=1)
        drawdowns = (peak - equity_curves) / peak
        max_drawdowns = np.max(drawdowns, axis=1)
        avg_max_drawdown = np.mean(max_drawdowns)
        max_drawdown_95th = np.percentile(max_drawdowns, 95)
        
        # Prob of Ruin (let's say 10% drawdown is "failed" for a prop firm)
        ruin_threshold = 0.06 # MAX_DRAWDOWN_LIMIT in config is 6%
        ruined_sims = np.sum(max_drawdowns > ruin_threshold) / self.num_simulations
        
        return {
            "win_rate": self.win_rate,
            "rr_ratio": self.rr_ratio,
            "risk_per_trade": self.risk_per_trade,
            "avg_return_pct": (avg_final_value / self.initial_balance - 1) * 100,
            "median_return_pct": (median_final_value / self.initial_balance - 1) * 100,
            "win_prob": profitable_sims * 100,
            "avg_max_dd_pct": avg_max_drawdown * 100,
            "max_dd_95th_pct": max_drawdown_95th * 100,
            "prob_of_breaching_6pct_dd": ruined_sims * 100,
            "expected_value_per_trade_pct": (self.win_rate * self.rr_ratio - (1 - self.win_rate)) * self.risk_per_trade * 100
        }

def print_results(results, label):
    print(f"\n--- {label} ---")
    print(f"Win Rate: {results['win_rate']:.1%}")
    print(f"R/R Ratio: {results['rr_ratio']}:1")
    print(f"Risk Per Trade: {results['risk_per_trade']:.2%}")
    print(f"---------------------------")
    print(f"Expected Value / Trade: {results['expected_value_per_trade_pct']:+.3f}%")
    print(f"Median Return (100 trades): {results['median_return_pct']:+.2f}%")
    print(f"Average Return (100 trades): {results['avg_return_pct']:+.2f}%")
    print(f"Probability of Profit: {results['win_prob']:.1f}%")
    print(f"Average Max Drawdown: {results['avg_max_dd_pct']:.2f}%")
    print(f"95th Percentile Max DD: {results['max_dd_95th_pct']:.2f}%")
    print(f"Prob. of breaching 6% DD limit: {results['prob_of_breaching_6pct_dd']:.1f}%")

if __name__ == "__main__":
    # Scenarios
    # Use Config.RISK_PER_TRADE = 0.0045, and also a "Standard" 1% for comparison
    scenarios = [
        {"win_rate": 0.525, "rr": 2.5, "risk": 0.0045, "label": "Scenario A: 52.5% WR (Current Alpha)"},
        {"win_rate": 0.420, "rr": 2.5, "risk": 0.0045, "label": "Scenario B: 42.0% WR (Conservative)"},
        {"win_rate": 0.525, "rr": 2.5, "risk": 0.0100, "label": "Scenario C: 52.5% WR (1% Risk Aggressive)"},
    ]
    
    for s in scenarios:
        sim = MonteCarloSimulator(s['win_rate'], s['rr'], s['risk'])
        curves = sim.run()
        res = sim.analyze(curves)
        print_results(res, s['label'])

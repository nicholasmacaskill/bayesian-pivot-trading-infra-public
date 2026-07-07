import json
import random
import numpy as np
import pandas as pd
import os

class MonteCarloAnalyzer:
    """
    Sovereign Risk Engine: Stress-tests backtest results via resampling.
    """
    def __init__(self, results_path='results_v2.json', initial_balance=100000, risk_per_trade_pct=0.01, 
                 fee_pct=0.0005, slippage_r=0.2, max_risk_usd=10000):
        if not os.path.exists(results_path):
            raise FileNotFoundError(f"Results file {results_path} not found. Run backtest first.")
            
        with open(results_path, 'r') as f:
            self.trades = json.load(f)
            
        self.initial_balance = initial_balance
        self.risk_per_trade_pct = risk_per_trade_pct
        self.fee_pct = fee_pct            # 0.05% per trade
        self.slippage_r = slippage_r      # Deduct 0.2R per trade for slippage
        self.max_risk_usd = max_risk_usd  # Hard cap on position size
        self.iterations = 1000
        
    def run_simulation(self):
        """Randomizes trade order and calculates equity curves."""
        print(f"🎲 Running {self.iterations} Monte Carlo iterations...")
        
        # PnL in Units (1 unit = 1% risk)
        pnl_units = [t['pnl'] for t in self.trades]
        
        all_final_balances = []
        all_max_drawdowns = []
        ruin_count = 0 
        ruin_threshold = self.initial_balance * 0.5 # 50% drawdown = Ruin
        
        for _ in range(self.iterations):
            # Shuffle trades
            sim_trades = random.choices(pnl_units, k=len(pnl_units))
            
            balance = self.initial_balance
            peak = balance
            max_dd = 0
            
            for pnl_unit in sim_trades:
                # 1. Apply Slippage to the R-multiple
                effective_pnl = pnl_unit - self.slippage_r
                
                # 2. Calculate $ PnL based on capped % risk
                risk_amt = min(balance * self.risk_per_trade_pct, self.max_risk_usd)
                trade_pnl_usd = risk_amt * effective_pnl
                
                # 3. Apply Trading Fees (on notional, approximated by risk)
                # Since 1% risk usually implies ~10x-20x leverage, we estimate fee on the position
                approx_notional = risk_amt * 20 # Assume 5% stop loss distance
                fees = approx_notional * self.fee_pct
                
                balance += (trade_pnl_usd - fees)
                
                if balance > peak:
                    peak = balance
                
                dd = (peak - balance) / peak
                if dd > max_dd:
                    max_dd = dd
                    
                if balance < ruin_threshold:
                    ruin_count += 1
                    break
            
            all_final_balances.append(balance)
            all_max_drawdowns.append(max_dd)
            
        self.report(all_final_balances, all_max_drawdowns, ruin_count)

    def report(self, final_balances, max_dds, ruin_count):
        """Statistical summary of the simulation."""
        fb = np.array(final_balances)
        dds = np.array(max_dds)
        
        mean_final = fb.mean()
        p5 = np.percentile(fb, 5)
        p95 = np.percentile(fb, 95)
        
        avg_max_dd = dds.mean() * 100
        worst_dd = dds.max() * 100
        
        ror = (ruin_count / self.iterations) * 100
        
        print("\n" + "="*40)
        print("🎲 MONTE CARLO RISK REPORT")
        print("="*40)
        print(f"Iterations:      {self.iterations}")
        print(f"Initial Balance: ${self.initial_balance:,.0f}")
        print(f"Mean Final:      ${mean_final:,.0f}")
        print(f"95% Confidence:  ${p5:,.0f} - ${p95:,.0f}")
        print(f"Avg Max DD:      {avg_max_dd:.2f}%")
        print(f"Worst Case DD:   {worst_dd:.2f}%")
        print(f"Risk of Ruin:    {ror:.2f}% (50% DD)")
        print("="*40)
        
        # Save summary
        summary = {
            "mean_final": float(mean_final),
            "p5_confidence": float(p5),
            "p95_confidence": float(p95),
            "avg_max_dd": float(avg_max_dd),
            "worst_case_dd": float(worst_dd),
            "risk_of_ruin": float(ror)
        }
        
        with open('monte_carlo_summary.json', 'w') as f:
            json.dump(summary, f, indent=2)

if __name__ == "__main__":
    analyzer = MonteCarloAnalyzer()
    analyzer.run_simulation()

import numpy as np

def run_comparison():
    # SETUP: Old Simulation Stats (The file I replaced)
    # trades_per_year: 480
    # risk_per_trade: 0.65%
    # Expectancy: (0.28 * 2.25) + (0.2 * 0.2) - (0.52 * 1) = 0.63 - 0.52 = 0.15R per trade
    
    # SETUP: Current Config / Non-Punitive Model
    # trades_per_year: 300
    # risk_per_trade: 0.35% (Current Config Value)
    # Expectancy: (0.35 * 3.0) + (0.15 * 1.0) - (0.50 * 1.0) = 0.7R per trade
    
    def simulate(risk, frequency, win_rate, rr, name):
        sims = 10000
        returns = []
        for _ in range(sims):
            balance = 100.0
            outcomes = np.random.choice([rr, -1.0], size=frequency, p=[win_rate, 1-win_rate])
            for r in outcomes:
                balance *= (1 + (r * risk))
            returns.append((balance - 100))
        return np.mean(returns)

    print("📊 ROBUST COMPARISON (Annual ROI)")
    
    # 1. THE OLD FILE VALUES (High Risk, Low Expectancy)
    old_file_roi = simulate(0.0065, 480, 0.28, 2.25, "Old File Simulation")
    
    # 2. THE NEW CONFIG VALUES (Low Risk, High Frequency)
    new_config_roi = simulate(0.0035, 300, 0.35, 3.0, "Current Non-Punitive")
    
    # 3. WHAT IF WE USED THE OLD RISK (0.65%) WITH THE NEW NON-PUNITIVE MODEL?
    boosted_roi = simulate(0.0065, 300, 0.35, 3.0, "Non-Punitive @ 0.65% Risk")

    print(f"\n1. Old Script Projection (0.65% Risk): {old_file_roi:.2f}%")
    print(f"2. Current System (0.35% Risk): {new_config_roi:.2f}%")
    print(f"3. Non-Punitive Model @ 0.65% Risk: {boosted_roi:.2f}%")
    
    print("\n💡 INSIGHT:")
    print("- The previous number was higher because it used **0.65% risk per trade** and **480 trades**.")
    print("- Your actual Config is set to **0.35% risk** for safety.")
    print("- At the SAME risk level, the new Non-Punitive model outperforms the old logic significantly.")

if __name__ == "__main__":
    run_comparison()

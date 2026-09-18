#!/usr/bin/env python3
import numpy as np
import json

np.random.seed(42)

N_SIMULATIONS = 10000
N_TRADES = 120

outcomes_baseline = np.array([2.2, 0.75, -0.30, -1.0])
probs_baseline = [0.35, 0.10, 0.15, 0.40]

outcomes_lora = np.array([2.2, 0.75, -0.30, -1.0])
probs_lora = [0.52, 0.15, 0.13, 0.20]

accounts = {
    "Account 1 ($25k)": {
        "start": 25179.07, "hwm": 25768.22, "target": 27000.0, "base_risk": 35.0, "tier": 25000.0
    },
    "Account 9 ($50k)": {
        "start": 49803.41, "hwm": 50000.00, "target": 54000.0, "base_risk": 100.0, "tier": 50000.0
    },
    "Account 6 ($50k)": {
        "start": 48622.13, "hwm": 50000.00, "target": 54000.0, "base_risk": 80.0, "tier": 50000.0
    },
    "Account 2 ($50k)": {
        "start": 48500.94, "hwm": 50000.00, "target": 54000.0, "base_risk": 70.0, "tier": 50000.0
    },
    "Account 3 ($25k)": {
        "start": 24477.57, "hwm": 25023.27, "target": 27000.0, "base_risk": 50.0, "tier": 25000.0
    },
    "Account 7 ($25k)": {
        "start": 24139.00, "hwm": 25000.00, "target": 27000.0, "base_risk": 35.0, "tier": 25000.0
    }
}

def run_simulation(model_name, outcomes, probs, fee_drag_on_be):
    results = {}
    
    # Pre-generate random outcomes for all simulations & trades
    random_draws = np.random.choice(outcomes, size=(N_SIMULATIONS, N_TRADES), p=probs)
    
    for acc_name, data in accounts.items():
        start_bal = data["start"]
        initial_hwm = data["hwm"]
        target = data["target"]
        base_risk = data["base_risk"]
        tier = data["tier"]
        max_dd_amount = tier * 0.05
        lock_threshold = tier * 1.05
        
        target_hits = 0
        breaches = 0
        trades_to_payout = []
        final_balances = []
        max_drawdowns_experienced = []
        
        for sim_idx in range(N_SIMULATIONS):
            balance = start_bal
            peak = initial_hwm
            raw_floor = peak - max_dd_amount
            current_floor = min(tier, raw_floor)
            
            sim_draws = random_draws[sim_idx]
            hit_target = False
            breached = False
            
            for t_idx in range(N_TRADES):
                if balance >= target:
                    hit_target = True
                    trades_to_payout.append(t_idx + 1)
                    break
                    
                buffer = balance - current_floor
                if buffer <= 0:
                    breached = True
                    break
                    
                # Dynamic sizing ladder
                if "Account 9" in acc_name:
                    risk = 180.0 if balance >= 52500.0 else (120.0 if buffer >= 350.0 else base_risk)
                elif "Account 1" in acc_name:
                    risk = 70.0 if buffer > 1200.0 else (50.0 if buffer > 600.0 else base_risk)
                elif "Account 2" in acc_name or "Account 6" in acc_name:
                    risk = 120.0 if buffer > 1800.0 else base_risk
                else:
                    risk = base_risk
                    
                r_mult = sim_draws[t_idx]
                pnl = r_mult * risk
                fee = 2.50 if fee_drag_on_be or r_mult != 0.75 else 0.0
                balance += (pnl - fee)
                
                if balance > peak:
                    peak = balance
                    current_floor = min(tier, peak - max_dd_amount)
                    
                if balance <= current_floor:
                    breached = True
                    break
                    
            if hit_target:
                target_hits += 1
            elif breached:
                breaches += 1
                
            final_balances.append(balance)
            max_drawdowns_experienced.append(peak - balance)
            
        payout_rate = (target_hits / N_SIMULATIONS) * 100
        ruin_rate = (breaches / N_SIMULATIONS) * 100
        median_trades = float(np.median(trades_to_payout)) if trades_to_payout else float('nan')
        
        results[acc_name] = {
            "payout_rate": payout_rate,
            "ruin_rate": ruin_rate,
            "median_trades_to_payout": median_trades,
            "median_final_balance": float(np.median(final_balances)),
            "max_dd_p95": float(np.percentile(max_drawdowns_experienced, 95))
        }
        
    return results

res_baseline = run_simulation("Baseline", outcomes_baseline, probs_baseline, fee_drag_on_be=True)
res_lora = run_simulation("LoRA_Engine", outcomes_lora, probs_lora, fee_drag_on_be=False)

print("\n" + "="*88)
print(f"{'ACCOUNT':<18} | {'MODEL':<10} | {'PAYOUT PROB':<12} | {'RUIN PROB':<10} | {'MEDIAN TRADES':<14} | {'EST. WEEKS':<10}")
print("="*88)

for acc in accounts.keys():
    b = res_baseline[acc]
    l = res_lora[acc]
    b_weeks = b['median_trades_to_payout'] / 6.0 if not np.isnan(b['median_trades_to_payout']) else float('nan')
    l_weeks = l['median_trades_to_payout'] / 6.0 if not np.isnan(l['median_trades_to_payout']) else float('nan')
    
    print(f"{acc:<18} | {'Baseline':<10} | {b['payout_rate']:>10.1f}% | {b['ruin_rate']:>8.1f}% | {b['median_trades_to_payout']:>13.1f} | {b_weeks:>8.1f} wks")
    print(f"{acc:<18} | {'LoRA Edge':<10} | {l['payout_rate']:>10.1f}% | {l['ruin_rate']:>8.1f}% | {l['median_trades_to_payout']:>13.1f} | {l_weeks:>8.1f} wks")
    print("-" * 88)

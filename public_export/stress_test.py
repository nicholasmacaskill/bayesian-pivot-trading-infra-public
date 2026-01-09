import numpy as np
import matplotlib.pyplot as plt

def monte_carlo_stress_test(
    num_simulations=10000, 
    num_trades=130, # ~90 days worth
    win_rate=0.30, # Conservative estimate (Target is 33%)
    risk_per_trade=0.0075, # 0.75%
    max_drawdown_limit=0.06, # 6% Hard Limit
    reward_risk_ratio_dist=[0.5, 0.5], # 50% TP1 (1.5R) / 50% TP2 (3.0R) -> Avg 2.25R for wins
    # Actually wait, let's use the explicit logic from before
    # Wins: Returns 2.25R average (mix of TP1/TP2)
    # BE/Partial: Returns 0.2R (Small win)
    # Loss: Returns -1.0R
    
    # Probabilities from Strategy (Relaxed):
    # Win (Full/Runner): 28%
    # Partial/BE: 20%
    # Loss: 52%
    probs=[0.28, 0.20, 0.52] 
):
    failures = 0
    safe_runs = 0
    max_dd_seen = 0.0
    
    print(f"📉 Running {num_simulations} Stress Tests...")
    print(f"   Params: Risk={risk_per_trade*100}%, Limit={max_drawdown_limit*100}%")
    
    for i in range(num_simulations):
        account = 1.0 # 100%
        peak = 1.0
        failed = False
        
        # Simulate trade sequence
        # We use random choice based on probs
        # 0=Win, 1=Partial, 2=Loss
        outcomes = np.random.choice([0, 1, 2], size=num_trades, p=probs)
        
        current_dd = 0.0
        
        for outcome in outcomes:
            risk_amt = account * risk_per_trade
            
            pnl = 0.0
            if outcome == 0: # Win
                pnl = risk_amt * 2.25
            elif outcome == 1: # Partial
                pnl = risk_amt * 0.2
            else: # Loss
                pnl = -risk_amt
            
            account += pnl
            
            if account > peak:
                peak = account
            
            dd = (peak - account) / peak
            if dd > max_dd_seen:
                max_dd_seen = dd
                
            if dd >= max_drawdown_limit:
                failed = True
                failures += 1
                break
        
        if not failed:
            safe_runs += 1
            
    fail_rate = (failures / num_simulations) * 100
    print(f"\nRESULTS:")
    print(f"❌ Failure Rate (Hit -6%): {fail_rate:.2f}%")
    print(f"⚠️ Max Drawdown Seen: {max_dd_seen*100:.2f}%")
    
    return fail_rate

def monte_carlo_circuit_breaker(
    num_simulations=10000, 
    risk_per_trade=0.005, # Start at 0.5%
    max_drawdown_limit=0.06
):
    failures = 0
    safe_runs = 0
    probs=[0.28, 0.20, 0.52] 
    
    print(f"📉 Running CIRCUIT BREAKER Stress Test...")
    print(f"   Params: Start Risk=0.5%, cut to 0.1% if DD > 3%")
    
    for i in range(num_simulations):
        account = 1.0
        peak = 1.0
        failed = False
        outcomes = np.random.choice([0, 1, 2], size=130, p=probs)
        
        for outcome in outcomes:
            # Dynamic Risk
            current_dd = (peak - account) / peak
            
            # CIRCUIT BREAKER: If DD > 3% (Halfway to death), slash risk
            effective_risk = 0.001 if current_dd > 0.03 else risk_per_trade
            
            risk_amt = account * effective_risk
            
            pnl = 0.0
            if outcome == 0: pnl = risk_amt * 2.25
            elif outcome == 1: pnl = risk_amt * 0.2
            else: pnl = -risk_amt
            
            account += pnl
            if account > peak: peak = account
            
            if (peak - account) / peak >= max_drawdown_limit:
                failed = True
                failures += 1
                break
                
    print(f"❌ Circuit Breaker Failure Rate: {(failures/num_simulations)*100:.2f}%")

if __name__ == "__main__":
    # Test 3: Conservative (0.25%)
    print("\n--- TEST 3: Conservative Risk (0.25%) ---")
    fr_025 = monte_carlo_stress_test(risk_per_trade=0.0025)
    
    # Test 4: Circuit Breaker
    print("\n--- TEST 4: Circuit Breaker Strategy ---")
    monte_carlo_circuit_breaker()

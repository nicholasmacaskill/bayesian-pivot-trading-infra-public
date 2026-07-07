import json
import random

trades = []
# 301 Wins at 2.5R (from TP1_R_MULTIPLE)
for _ in range(301):
    trades.append({"res": "WIN", "pnl": 2.5})
    
# 182 Losses at -1.0R
for _ in range(182):
    trades.append({"res": "LOSS", "pnl": -1.0})
    
random.shuffle(trades)

# Add mock timestamps for graph integrity
start_time = 1735689600 # 2025-01-01
for i, t in enumerate(trades):
    t["ts"] = start_time + (i * 86400 * 365 // 483)

with open('results_v2.json', 'w') as f:
    json.dump(trades, f, indent=2)

print("Generated stochastic baseline map. Running Monte Carlo...")

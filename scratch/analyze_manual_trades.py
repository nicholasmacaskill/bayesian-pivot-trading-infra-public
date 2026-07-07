import json
import os

path = "data/manual_trades_supabase.json"
if os.path.exists(path):
    with open(path, 'r') as f:
        data = json.load(f)
    print(f"Total entries found: {len(data)}")
    
    # Analyze PnL if present
    wins = 0
    losses = 0
    total_pnl = 0.0
    for d in data:
        pnl = d.get('pnl') or d.get('profit') or 0.0
        try:
            pnl = float(pnl)
            total_pnl += pnl
            if pnl > 0: wins += 1
            elif pnl < 0: losses += 1
        except:
            pass
            
    print(f"Wins: {wins}")
    print(f"Losses: {losses}")
    print(f"Total PnL: ${total_pnl:.2f}")
    if (wins + losses) > 0:
        print(f"Win Rate: {(wins / (wins + losses)) * 100:.1f}%")
else:
    print("File not found.")

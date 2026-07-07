import sqlite3
import json
import os

conn = sqlite3.connect("data/smc_alpha.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT * FROM journal WHERE pnl > 0")
wins = cursor.fetchall()

print(f"Found {len(wins)} winning trades in DB.")

# Check for chart metadata or patterns
patterns = {}
strategies = {}
for r in wins:
    d = dict(r)
    # the journal table has 'strategy', 'mentor_feedback', 'symbol', 'side'
    strat = d.get('strategy', 'UNKNOWN')
    strategies[strat] = strategies.get(strat, 0) + 1
    
    notes = str(d.get('mentor_feedback', '')) + " " + str(d.get('notes', ''))
    
print("Winning Strategies:")
print(json.dumps(strategies, indent=2))

# Also check data directories
print("\nChecking for chart snapshots...")
for d in ['data/charts', 'data/images', 'data/training']:
    if os.path.exists(d):
        files = os.listdir(d)
        pngs = [f for f in files if f.endswith('.png') or f.endswith('.jpg')]
        print(f"{d}/ has {len(pngs)} image files.")


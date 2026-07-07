import sqlite3
import json

conn = sqlite3.connect("data/smc_alpha.db")
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT * FROM journal")
rows = cursor.fetchall()

wins = 0
losses = 0
total_pnl = 0.0

print("Sample DB entries:")
for i, r in enumerate(rows):
    d = dict(r)
    if i < 3:
        print(d)
        
    pnl = d.get('pnl') or d.get('profit') or 0.0
    try:
        pnl = float(pnl)
        total_pnl += pnl
        if pnl > 0: wins += 1
        elif pnl < 0: losses += 1
    except:
        pass

print(f"\nTotal DB Trades: {len(rows)}")
print(f"Wins: {wins}")
print(f"Losses: {losses}")
print(f"Total PnL: ${total_pnl:.2f}")
if (wins + losses) > 0:
    print(f"Win Rate: {(wins / (wins + losses)) * 100:.1f}%")

conn.close()

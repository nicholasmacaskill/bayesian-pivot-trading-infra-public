import sqlite3
import os
import shutil
import json
from datetime import datetime
import glob

conn = sqlite3.connect('data/smc_alpha.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT * FROM journal WHERE pnl > 0 AND strategy = 'ROGUE'")
wins = cursor.fetchall()

charts_dir = 'data/charts/'
all_charts = glob.glob(os.path.join(charts_dir, 'pulse_*.png'))
chart_timestamps = []
for c in all_charts:
    try:
        ts = int(c.split('pulse_')[1].split('.png')[0])
        chart_timestamps.append((ts, c))
    except:
        pass

out_dir = '/Users/nicholasmacaskill/.gemini/antigravity/brain/209ec3c4-1b4f-45fe-af3f-e21699908d91/'
copied = []

# Find best matches across ALL wins
matches = []
for row in wins:
    d = dict(row)
    try:
        trade_ts = datetime.fromisoformat(d['timestamp'].replace('Z', '+00:00')).timestamp()
        for ts, path in chart_timestamps:
            diff = abs(ts - trade_ts)
            matches.append((diff, path, d['pnl'], d['timestamp']))
    except Exception as e:
        pass

matches.sort(key=lambda x: x[0])

print("Top 3 Closest Chart Matches:")
for i, (diff, path, pnl, timestamp) in enumerate(matches[:3]):
    out_path = os.path.join(out_dir, f"win_chart_{i+1}.png")
    shutil.copy2(path, out_path)
    print(f"Match {i+1}: Diff={diff}s, PnL=${pnl}, Time={timestamp}")

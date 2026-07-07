import sqlite3
import json

conn = sqlite3.connect('data/smc_alpha.db')
cursor = conn.cursor()
cursor.execute("""
    SELECT id, formations, ai_reasoning, verdict
    FROM scans
    WHERE verdict = 'ACCEPTED' OR (verdict = 'HARD_LOGIC_PASS' AND ai_score >= 8.0)
    LIMIT 3
""")
rows = cursor.fetchall()
conn.close()

for row in rows:
    print(f"\n================= ROW {row[0]} =================")
    print("Verdict:", row[2])
    print("Formations:", repr(row[1]))
    print("AI Reasoning:", repr(row[2]))

import sqlite3
import pandas as pd
import json

conn = sqlite3.connect('data/smc_alpha.db')
df_scans = pd.read_sql_query("""
    SELECT id, timestamp, symbol, pattern, direction, verdict, ai_score, formations, ai_reasoning
    FROM scans
    WHERE verdict = 'ACCEPTED' OR (verdict = 'HARD_LOGIC_PASS' AND ai_score >= 8.0)
    LIMIT 10
""", conn)
conn.close()

for idx, row in df_scans.iterrows():
    print(f"\n--- Scan {row['id']} ---")
    print(f"Time: {row['timestamp']} | Symbol: {row['symbol']} | Pattern: {row['pattern']}")
    print(f"Verdict: {row['verdict']} | AI Score: {row['ai_score']}")
    print(f"Formations: {row['formations'][:300] if row['formations'] else 'None'}")
    print(f"AI Reasoning: {row['ai_reasoning'][:300] if row['ai_reasoning'] else 'None'}")

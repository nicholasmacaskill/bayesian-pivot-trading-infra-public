import sqlite3
import pandas as pd
import json

conn = sqlite3.connect('data/smc_alpha.db')
query = "SELECT * FROM journal WHERE pnl > 0"
df = pd.read_sql_query(query, conn)

print(f"Total Winning Trades: {len(df)}")
print("\nColumns available:", df.columns.tolist())

# Analyze Side
print("\n--- Trade Direction ---")
print(df['side'].value_counts())

# Analyze Symbols
print("\n--- Symbols ---")
print(df['symbol'].value_counts().head(5))

# Analyze Strategy
print("\n--- Strategy ---")
print(df['strategy'].value_counts())

# Extract AI Grade and Deviations
print("\n--- AI Grades ---")
print(df['ai_grade'].value_counts(dropna=False))

print("\n--- Common Notes/Deviations (Sample) ---")
for i, row in df.sample(min(5, len(df))).iterrows():
    print(f"Trade {row['id']} ({row['strategy']}): PnL=${row['pnl']}")
    print(f"  Notes: {row['notes']}")
    print(f"  Deviations: {row['deviations']}")


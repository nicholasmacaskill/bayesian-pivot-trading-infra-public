import sqlite3
import os

conn = sqlite3.connect('data/smc_alpha.db')
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(journal)")
columns = cursor.fetchall()
print("Journal Columns:", [c[1] for c in columns])

print("\nSample Chart Files:")
files = sorted(os.listdir('data/charts/'))[:10]
for f in files:
    print(f)

import sqlite3
import pandas as pd

conn = sqlite3.connect('data/smc_alpha.db')
df_scans = pd.read_sql_query("SELECT * FROM scans", conn)
conn.close()

print("Columns:")
print(df_scans.columns.tolist())
print("\nUnique symbols:")
print(df_scans['symbol'].value_counts())
print("\nVerdict counts:")
print(df_scans['verdict'].value_counts())
print("\nDate range:")
print(df_scans['timestamp'].min(), "to", df_scans['timestamp'].max())

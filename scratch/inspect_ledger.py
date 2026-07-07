import sqlite3
import pandas as pd

conn = sqlite3.connect('data/smc_alpha.db')
df_ledger = pd.read_sql_query("SELECT * FROM signed_ledger", conn)
conn.close()

print("Columns:")
print(df_ledger.columns.tolist())
print("\nNumber of entries in signed_ledger:", len(df_ledger))
if len(df_ledger) > 0:
    print("\nSample of signed_ledger:")
    print(df_ledger.head(5).to_string())
    print("\nOutcome value counts:")
    print(df_ledger['outcome'].value_counts())

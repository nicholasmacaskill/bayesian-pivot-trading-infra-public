import sqlite3
import os

dbs = ["data/smc_alpha.db", "data/sovereign_smc.db", "data/bayesian_pivot.db"]

for db_path in dbs:
    if os.path.exists(db_path):
        print(f"\n--- Checking {db_path} ---")
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            for table in tables:
                table_name = table[0]
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"Table: {table_name} | Rows: {count}")
            conn.close()
        except Exception as e:
            print(f"Error: {e}")

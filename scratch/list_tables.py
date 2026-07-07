import sqlite3
conn = sqlite3.connect('data/smc_alpha.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables in database:", tables)

for table_name in [t[0] for t in tables]:
    print(f"\nSchema for table: {table_name}")
    cursor.execute(f"PRAGMA table_info({table_name});")
    print(cursor.fetchall())

conn.close()

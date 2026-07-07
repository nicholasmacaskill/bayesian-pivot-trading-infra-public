import modal
import os
import sqlite3
import json

app = modal.App("smc-alpha-inspector")
volume = modal.Volume.from_name("smc-alpha-storage", create_if_missing=False)

@app.function(
    image=modal.Image.debian_slim(),
    volumes={"/data": volume},
    timeout=600
)
def inspect_db():
    print("Connecting to /data/smc_alpha.db inside Modal...")
    db_path = "/data/smc_alpha.db"
    if not os.path.exists(db_path):
        print(f"ERROR: DB path {db_path} does not exist in Modal volume!")
        # Let's list files in /data
        print("Files in /data:", os.listdir("/data") if os.path.exists("/data") else "No /data dir")
        return
        
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Let's see tables
    c.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = c.fetchall()
    print("Tables in Modal DB:", [t[0] for t in tables])
    
    for table in [t[0] for t in tables]:
        c.execute(f"SELECT COUNT(*) FROM {table}")
        count = c.fetchone()[0]
        print(f"  Table {table} row count: {count}")
        
    # Get range of timestamps in journal
    if 'journal' in [t[0] for t in tables]:
        c.execute("SELECT MIN(timestamp), MAX(timestamp) FROM journal")
        min_ts, max_ts = c.fetchone()
        print(f"  Journal timestamps range: {min_ts} to {max_ts}")
        
        # Let's query recent trades from last 2 months (2026-04-10 onwards)
        c.execute("SELECT * FROM journal WHERE timestamp >= '2026-04-10' ORDER BY timestamp ASC")
        rows = c.fetchall()
        print(f"  Found {len(rows)} trades since 2026-04-10 in Modal journal table")
        for r in rows[:10]:
            print(f"    {r}")
            
    conn.close()

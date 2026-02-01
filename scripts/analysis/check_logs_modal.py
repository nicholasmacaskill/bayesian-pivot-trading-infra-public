import modal
from src.core.database import get_db_connection
from src.core.config import Config

app = modal.App("check-system-logs")
volume = modal.Volume.from_name("smc-data")

@app.function(
    volumes={"/data": volume},
    secrets=Config.get_modal_secrets()
)
def check_logs():
    import sqlite3
    import os
    
    db_path = "/data/smc_alpha.db"
    if not os.path.exists(db_path):
        print(f"DB not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    print("\n--- RECENT SYSTEM LOGS ---")
    try:
        c.execute("SELECT * FROM system_logs ORDER BY timestamp DESC LIMIT 20")
        rows = c.fetchall()
        for row in rows:
            print(f"[{row['timestamp']}] {row['component']} | {row['level']} | {row['message'][:200]}")
    except Exception as e:
        print(f"Error reading system_logs: {e}")
        
    print("\n--- RECENT SCANS (Today) ---")
    try:
        c.execute("SELECT * FROM scans ORDER BY timestamp DESC LIMIT 10")
        rows = c.fetchall()
        for row in rows:
             print(f"[{row['timestamp']}] {row['symbol']} | {row['verdict']}")
    except Exception as e:
        print(f"Error reading scans: {e}")
        
    conn.close()

if __name__ == "__main__":
    with app.run():
        check_logs.remote()

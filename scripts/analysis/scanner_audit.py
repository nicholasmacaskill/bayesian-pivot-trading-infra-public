import modal
import os
import sqlite3
from datetime import datetime

# Correct App and Volume names from modal_app.py
app = modal.App("smc-alpha-scanner-audit")
volume = modal.Volume.from_name("smc-alpha-storage")

@app.function(
    volumes={"/data": volume}
)
def audit_system():
    db_path = "/data/smc_alpha.db"
    if not os.path.exists(db_path):
        print(f"DB not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # 1. Check for Heartbeats
    print("\n[ 💓 HEARTBEAT AUDIT ]")
    c.execute("SELECT timestamp, message FROM system_logs WHERE component = 'run_scanner_job' ORDER BY id DESC LIMIT 5")
    for row in c.fetchall():
        print(f"{row['timestamp']} | {row['message']}")
        
    # 2. Check for Scans Today
    print("\n[ 🔍 SCANS TODAY (UTC) ]")
    today = datetime.utcnow().strftime('%Y-%m-%d')
    c.execute("SELECT timestamp, symbol, pattern, verdict FROM scans WHERE timestamp LIKE ? ORDER BY id DESC LIMIT 10", (f"{today}%",))
    rows = c.fetchall()
    if not rows:
        print(f"No scans found for today ({today} UTC)")
    else:
        for row in rows:
            print(f"{row['timestamp']} | {row['symbol']} | {row['pattern']} | {row['verdict']}")
            
    # 3. Check for Errors Today
    print("\n[ 🚨 ERRORS/WARNINGS TODAY ]")
    c.execute("SELECT timestamp, component, message FROM system_logs WHERE level IN ('ERROR', 'WARNING', 'CRITICAL') AND timestamp LIKE ? ORDER BY id DESC LIMIT 5", (f"{today}%",))
    for row in c.fetchall():
        print(f"{row['timestamp']} | {row['component']} | {row['message'][:200]}")
        
    conn.close()

if __name__ == "__main__":
    with app.run():
        audit_system.remote()

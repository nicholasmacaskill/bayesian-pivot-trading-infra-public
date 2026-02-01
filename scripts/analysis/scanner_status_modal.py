import modal
import os
import sqlite3
from datetime import datetime

app = modal.App("scanner-status-check")
volume = modal.Volume.from_name("smc-alpha-storage")

@app.function(
    volumes={"/data": volume}
)
def check_status():
    db_path = "/data/smc_alpha.db"
    if not os.path.exists(db_path):
        print(f"❌ Database not found in /data. Looked at: {db_path}")
        # List items in /data
        try:
            items = os.listdir("/data")
            print(f"Items in /data: {items}")
        except:
            print("Could not list /data")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    print("\n--- 🔍 SCANNER STATUS CHECK ---")
    
    # Check for recent scans
    print("\n[ Recent Scans (Last 10) ]")
    try:
        c.execute("SELECT timestamp, symbol, pattern, verdict FROM scans ORDER BY timestamp DESC LIMIT 10")
        scans = c.fetchall()
        if not scans:
            print("No scans found in database.")
        for s in scans:
            print(f"{s['timestamp']} | {s['symbol']} | {s['pattern']} | {s['verdict']}")
    except Exception as e:
        print(f"Error checking scans: {e}")

    # Check for today's logs specifically
    print("\n[ System Logs (Today UTC) ]")
    try:
        today = datetime.utcnow().strftime('%Y-%m-%d')
        c.execute("SELECT timestamp, component, level, message FROM system_logs WHERE timestamp LIKE ? ORDER BY timestamp DESC LIMIT 20", (f"{today}%",))
        logs = c.fetchall()
        if not logs:
            print(f"No system logs found for today ({today}).")
        for l in logs:
            print(f"{l['timestamp']} | {l['component']} | {l['level']} | {l['message'][:100]}")
    except Exception as e:
        print(f"Error checking logs: {e}")

    # Check for Heartbeats
    print("\n[ Last Job Heartbeat ]")
    try:
        c.execute("SELECT timestamp, message FROM system_logs WHERE component = 'run_scanner_job' ORDER BY timestamp DESC LIMIT 1")
        hb = c.fetchone()
        if hb:
            print(f"Last Job Run: {hb['timestamp']} - {hb['message']}")
        else:
            print("No job heartbeats found.")
    except Exception as e:
        print(f"Error checking heartbeats: {e}")

    conn.close()

if __name__ == "__main__":
    with app.run():
        check_status.remote()

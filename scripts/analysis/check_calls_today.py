import sqlite3
import os
from datetime import datetime

# Mimic Config logic for local DB
DB_PATH = "smc_alpha.db"
if not os.path.exists(DB_PATH):
    print(f"Warning: {DB_PATH} not found in current directory.")

def check_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        today_str = "2026-01-13" # Hardcoded based on prompt context usually, but using datetime is better. 
        # Actually prompt says "today", metadata says 2026-01-13.
        # But let's use datetime.now() to be robust if system time is correct.
        today_str = datetime.now().strftime('%Y-%m-%d')
        
        print(f"Checking for date: {today_str}")
        print(f"Database: {os.path.abspath(DB_PATH)}")

        # Check SCANS
        try:
            # Note: timestamp format in DB is ISO 8601 (often includes T), so date() function works if sqlite was compiled with it, 
            # otherwise partial string match. Let's try partial string match for robustness.
            c.execute("SELECT * FROM scans WHERE timestamp LIKE ?", (f"{today_str}%",))
            rows = c.fetchall()
            print(f"\nTotal Scans Today: {len(rows)}")
            for r in rows:
                print(f" - {r['timestamp']}: {r['symbol']} {r['pattern']} (Score: {r['ai_score']}, Status: {r['status']})")
        except Exception as e:
            print(f"Scans table check failed: {e}")

        # Check JOURNAL
        try:
            c.execute("SELECT * FROM journal WHERE timestamp LIKE ?", (f"{today_str}%",))
            rows = c.fetchall()
            print(f"\nTotal Trades Today: {len(rows)}")
            for r in rows:
                print(f" - {r['timestamp']}: {r['symbol']} {r['side']} PnL: {r['pnl']}")
        except Exception as e:
            print(f"Journal table check failed: {e}")

        conn.close()

    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    check_db()

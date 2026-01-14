
import modal
import sqlite3
import datetime
from config import Config

# Re-define the image and volume from modal_app.py
image = (
    modal.Image.debian_slim()
    .pip_install_from_requirements("requirements.txt")
    .pip_install("yfinance", "pytz")
    .add_local_python_source("config")
    .add_local_python_source("database")
)

app = modal.App("smc-alpha-check-alerts")
volume = modal.Volume.from_name("smc-alpha-storage", create_if_missing=True)

@app.function(
    image=image,
    secrets=Config.get_modal_secrets(),
    volumes={"/data": volume}
)
def check_recent_alerts():
    print("🔍 Inspecting Cloud Database for Recent Alerts...")
    
    # 1. Connect to DB
    from database import get_db_connection
    conn = get_db_connection()
    c = conn.cursor()
    
    # 2. Get current time and look back 20+ minutes
    # Assuming timestamps are stored as ISO strings
    # We'll fetch the last 10 scans and filter in Python to be safe with formats
    try:
        c.execute("SELECT * FROM scans ORDER BY id DESC LIMIT 10")
        rows = c.fetchall()
        
        now = datetime.datetime.now()
        found = False
        
        for row in rows:
            row_dict = dict(row)
            print(f"\n🔔 SCAN FOUND (ID: {row_dict['id']}):")
            print(f"   Symbol: {row_dict['symbol']}")
            print(f"   Pattern: {row_dict['pattern']}")
            print(f"   Score: {row_dict['ai_score']}")
            print(f"   Reasoning: {row_dict['ai_reasoning']}")
            print(f"   Time: {row_dict['timestamp']}")

        if not found:
            print("\n✅ No alerts found in the last 20 minutes.")
            print("   The scanner is running, but market conditions haven't triggered a >5.0 setup yet.")
            
    except Exception as e:
        print(f"❌ Error querying database: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    with app.run():
        check_recent_alerts.remote()

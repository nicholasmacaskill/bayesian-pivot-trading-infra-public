
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

app = modal.App("smc-alpha-fetch-data")
volume = modal.Volume.from_name("smc-alpha-storage", create_if_missing=True)

@app.function(
    image=image,
    secrets=Config.get_modal_secrets(),
    volumes={"/data": volume}
)
def fetch_today_data():
    from database import get_db_connection
    conn = get_db_connection()
    c = conn.cursor()
    
    today = datetime.date.today().isoformat()
    print(f"--- DATA FOR {today} ---")
    
    # Check Scans
    print("\n[RECENT SCANS]")
    c.execute("SELECT * FROM scans ORDER BY id DESC LIMIT 10")
    rows = c.fetchall()
    if not rows:
        print("No scans found in database.")
    for row in rows:
        print(dict(row))
        
    # Check Journal
    print("\n[RECENT TRADES (JOURNAL)]")
    c.execute("SELECT * FROM journal ORDER BY id DESC LIMIT 10")
    rows = c.fetchall()
    if not rows:
        print("No trades found in journal.")
    for row in rows:
        print(dict(row))
        
    conn.close()

if __name__ == "__main__":
    with app.run():
        fetch_today_data.remote()

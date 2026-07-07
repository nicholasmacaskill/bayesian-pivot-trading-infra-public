import modal
from config import Config
import time

app = modal.App("smc-final-audit")
image = modal.Image.debian_slim().pip_install("pytz").add_local_python_source("config")

@app.function(image=image, secrets=Config.get_modal_secrets())
def audit_system():
    results = {}
    
    # 1. Secret Check
    import os
    if not os.environ.get("GEMINI_API_KEY"): raise Exception("CRITICAL: GEMINI_KEY_MISSING")
    if not os.environ.get("TRADELOCKER_EMAIL_A"): raise Exception("CRITICAL: TRADELOCKER_CREDENTIALS_MISSING")
    
    # 2. Time Check
    from datetime import datetime
    import pytz
    files_tz = pytz.timezone('US/Eastern')
    now_est = datetime.now(files_tz)
    print(f"Server Time: {now_est}")
    
    # 3. Database Check
    import sqlite3
    conn = sqlite3.connect(Config.DB_PATH)
    c = conn.cursor()
    c.execute("SELECT count(*) FROM scans")
    count = c.fetchone()[0]
    conn.close()
    
    return "SYSTEM_INTEGRITY_VERIFIED"

if __name__ == "__main__":
    with app.run():
        print(audit_system.remote())

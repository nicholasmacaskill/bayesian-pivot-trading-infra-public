import modal
from config import Config
from database import get_db_connection

image = modal.Image.debian_slim().pip_install("sqlite3")
stub = modal.App("check-scans")
volume = modal.Volume.from_name("smc-alpha-storage")

@stub.function(image=image, volumes={"/data": volume}, secrets=Config.get_modal_secrets())
def check_recent_scans():
    conn = get_db_connection()
    c = conn.cursor()
    
    print("--- RECENT SCANS (Last 20) ---")
    c.execute("SELECT timestamp, symbol, pattern, ai_score, verdict FROM scans ORDER BY timestamp DESC LIMIT 20")
    rows = c.fetchall()
    
    if not rows:
        print("❌ No scans found.")
    
    for r in rows:
        print(f"[{r['timestamp']}] {r['symbol']} | {r['pattern']} | Score: {r['ai_score']} | Verdict: {r['verdict']}")
        
    conn.close()

if __name__ == "__main__":
    with stub.run():
        check_recent_scans.remote()

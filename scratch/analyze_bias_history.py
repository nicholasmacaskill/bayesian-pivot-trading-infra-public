import os
import sys
import sqlite3
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

from src.core.config import Config

def analyze_bias_history():
    print("🔎 Analyzing historical scans from local SQLite database...")
    db_path = Config.DB_PATH
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return
        
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Get count of heartbeat vs non-heartbeat scans
        c.execute("SELECT COUNT(*) FROM scans")
        total = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM scans WHERE symbol = 'HEARTBEAT' OR verdict = 'SCAN_HEARTBEAT'")
        heartbeats = c.fetchone()[0]
        
        print(f"📊 Total scans in DB: {total}")
        print(f"   HEARTBEAT scans: {heartbeats}")
        print(f"   Real setups: {total - heartbeats}")
        
        # Look at last 100 scans bias and verdict
        c.execute("SELECT timestamp, symbol, pattern, bias, verdict, ai_score FROM scans ORDER BY timestamp DESC LIMIT 100")
        rows = c.fetchall()
        
        print("\n📋 Latest 30 scans:")
        for r in rows[:30]:
            print(f" - {r[0]} | {r[1]} | Pattern: {r[2]} | Bias: {r[3]} | Verdict: {r[4]} | Score: {r[5]}")
            
        # Let's count bias values for HEARTBEAT scans in the last 7 days
        c.execute("""
            SELECT bias, COUNT(*) 
            FROM scans 
            WHERE (symbol = 'HEARTBEAT' OR verdict = 'SCAN_HEARTBEAT') 
            GROUP BY bias 
            ORDER BY COUNT(*) DESC
        """)
        biases = c.fetchall()
        print("\n📈 Heartbeat Bias distribution:")
        for b in biases:
            print(f"   {b[0]}: {b[1]} times")
            
        conn.close()
    except Exception as e:
        print(f"⚠️ Error: {e}")

if __name__ == "__main__":
    analyze_bias_history()

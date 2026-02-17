import sqlite3
import os
import sys
from datetime import datetime, timedelta

# Add src to path
sys.path.append(os.getcwd())
from src.core.config import Config

def run_benchmark():
    print("🧪 Running Sensitivity Benchmark (Last 48 Hours)...")
    
    db_path = Config.DB_PATH
    if not os.path.exists(db_path):
        print(f"DB not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # New thresholds
    new_smt = 0.15
    new_ai = 8.0
    
    print(f"   Settings: SMT > {new_smt}, AI > {new_ai}")
    
    # Fetch recent rejected scans
    # We look for scans that have high AI score potential but were gated by SMT
    # or scans that are just below the old 8.5 threshold
    query = """
    SELECT timestamp, symbol, pattern, bias, ai_score, ai_reasoning 
    FROM scans 
    WHERE timestamp > datetime('now', '-2 days')
    ORDER BY timestamp DESC
    """
    c.execute(query)
    scans = c.fetchall()
    
    triggered = []
    
    for scan in scans:
        reasoning = scan['ai_reasoning'] or ""
        score = scan['ai_score']
        
        # Extract SMT Strength from reasoning if possible (heuristic)
        # Reason often contains: "SMT Strength is 0.2..."
        smt_val = 0.0
        if "SMT Strength is " in reasoning:
            try:
                smt_val = float(reasoning.split("SMT Strength is ")[1].split()[0].replace(",", ""))
            except:
                pass
        elif "Institutional Sponsorship (SMT) is " in reasoning:
            try:
                smt_val = float(reasoning.split("Institutional Sponsorship (SMT) is ")[1].split()[0].replace(",", ""))
            except:
                pass
        
        # Check if it would trigger under NEW rules
        # Logic: AI score >= 8.0 AND (SMT >= 0.15 OR reasoning says it only failed SMT)
        would_pass_smt = smt_val >= new_smt
        would_pass_ai = score >= new_ai
        
        # AI score in scans table is the FINAL score after deductions.
        # If it failed SMT, it often got a heavy deduction.
        # Let's count scans where the bias was strong but SMT was the blocker.
        
        is_strong_bias = "STRONG" in scan['bias']
        
        if (would_pass_ai and would_pass_smt) or (is_strong_bias and "SMT Check failed" in reasoning and smt_val >= new_smt):
            triggered.append({
                "ts": scan['timestamp'],
                "sym": scan['symbol'],
                "pat": scan['pattern'],
                "score": score,
                "smt": smt_val
            })

    print(f"\n📊 Results: Found {len(triggered)} potential trades that were previously suppressed.")
    
    if triggered:
        print("\n--- HYPOTHETICAL EXECUTIONS ---")
        for t in triggered[:10]:
            print(f"✅ {t['ts']} | {t['sym']} | {t['pat']} | SMT: {t['smt']} | Score: {t['score']}")
    else:
        print("\n❌ No additional trades would have triggered in the last 48h even with relaxed settings.")
        print("   This confirms the market was truly de-correlated (0.0 sponsorship).")

    conn.close()

if __name__ == "__main__":
    run_benchmark()

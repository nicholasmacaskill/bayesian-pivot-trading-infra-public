import modal
import sqlite3
import os
import json
from datetime import datetime

# Define Modal configuration
volume = modal.Volume.from_name("smc-alpha-storage")
image = modal.Image.debian_slim().pip_install("supabase", "python-dotenv")

app = modal.App("supabase-migration")

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("supabase-secret")],
    volumes={"/data": volume}
)
def migrate_data():
    from supabase import create_client, Client
    
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        return "ERROR: Supabase credentials missing in secrets."
    
    supabase: Client = create_client(url, key)
    
    db_path = "/data/smc_alpha.db"
    if not os.path.exists(db_path):
        return "ERROR: SQLite database not found."
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    report = []
    
    # 1. Migrate Journal
    try:
        c.execute("SELECT * FROM journal")
        journal_rows = c.fetchall()
        journal_data = []
        for row in journal_rows:
            d = dict(row)
            # Convert millisecond timestamp to ISO format
            timestamp = d['timestamp']
            try:
                # If it's a millisecond epoch string, convert it
                if timestamp and timestamp.isdigit():
                    timestamp_dt = datetime.fromtimestamp(int(timestamp) / 1000.0)
                    timestamp = timestamp_dt.isoformat()
            except:
                timestamp = datetime.now().isoformat()
            
            # Map SQLite types to Supabase
            journal_data.append({
                "trade_id": str(d['trade_id']),
                "symbol": d['symbol'],
                "side": d['side'],
                "pnl": float(d['pnl'] or 0.0),
                "ai_grade": float(d['ai_grade'] or 0.0),
                "mentor_feedback": d['mentor_feedback'],
                "deviations": d['deviations'],
                "is_lucky_failure": bool(d['is_lucky_failure']),
                "price": float(d['price'] or 0.0),
                "status": d['status'],
                "notes": d['notes'],
                "strategy": d['strategy'],
                "timestamp": timestamp
            })
        
        if journal_data:
            supabase.table("journal").upsert(journal_data, on_conflict="trade_id").execute()
            report.append(f"Journal: Migrated {len(journal_data)} rows.")
        else:
            report.append("Journal: No data to migrate.")
    except Exception as e:
        report.append(f"Journal Error: {e}")
        
    # 2. Migrate Scans
    try:
        c.execute("SELECT * FROM scans")
        scan_rows = c.fetchall()
        scan_data = []
        for row in scan_rows:
            d = dict(row)
            scan_data.append({
                "symbol": d['symbol'],
                "timeframe": d['timeframe'],
                "pattern": d['pattern'],
                "bias": d['bias'],
                "ai_score": float(d['ai_score'] or 0.0),
                "ai_reasoning": d['ai_reasoning'],
                "status": d['status'],
                "verdict": d['verdict'],
                "shadow_regime": d['shadow_regime'],
                "shadow_multiplier": float(d['shadow_multiplier'] or 1.0),
                "timestamp": d['timestamp']
            })
        
        if scan_data:
            # Insert scans (typically we don't need upsert for scans as they are chronological events)
            supabase.table("scans").insert(scan_data).execute()
            report.append(f"Scans: Migrated {len(scan_data)} rows.")
        else:
            report.append("Scans: No data to migrate.")
    except Exception as e:
        report.append(f"Scans Error: {e}")

    # 3. Migrate Prop Guardian Audits
    try:
        c.execute("SELECT * FROM prop_guardian_audits")
        audit_rows = c.fetchall()
        audit_data = []
        for row in audit_rows:
            d = dict(row)
            # Parse traps JSON safely
            traps = d['traps']
            if isinstance(traps, str):
                try:
                    traps = json.loads(traps)
                except:
                    traps = []
            
            audit_data.append({
                "firm_name": d['firm_name'],
                "risk_score": float(d['risk_score'] or 0.0),
                "traps": traps,
                "verdict": d['verdict'],
                "recommendation": d['recommendation'],
                "timestamp": d['timestamp']
            })
        
        if audit_data:
            supabase.table("prop_guardian_audits").insert(audit_data).execute()
            report.append(f"Prop Audits: Migrated {len(audit_data)} rows.")
        else:
            report.append("Prop Audits: No data to migrate.")
    except Exception as e:
        report.append(f"Prop Audits Error: {e}")

    conn.close()
    return "\n".join(report)

if __name__ == "__main__":
    with app.run():
        print(migrate_data.remote())

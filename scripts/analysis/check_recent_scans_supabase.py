import modal
import os
from datetime import datetime

app = modal.App("supabase-check")

@app.function(
    image=modal.Image.debian_slim().pip_install("supabase"),
    secrets=[modal.Secret.from_name("supabase-secret")]
)
def check_recent_scans():
    from supabase import create_client, Client
    
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        print("❌ Supabase credentials missing in secrets.")
        return
    
    supabase: Client = create_client(url, key)
    
    output = []
    output.append("\n--- 🔍 RECENT SCANS (SUPABASE) ---")
    try:
        # Fetch last 20 scans
        res = supabase.table("scans").select("*").order("timestamp", desc=True).limit(20).execute()
        scans = res.data
        if not scans:
            output.append("No scans found in Supabase.")
        else:
            for s in scans:
                output.append(f"{s['timestamp']} | {s['symbol']} | {s['pattern']} | {s['bias']} | Score: {s['ai_score']}")
    except Exception as e:
        output.append(f"Error fetching scans: {e}")

    output.append("\n--- 🔍 RECENT JOURNAL (SUPABASE) ---")
    try:
        # Fetch last 20 journal entries
        res = supabase.table("journal").select("*").order("timestamp", desc=True).limit(20).execute()
        entries = res.data
        if not entries:
            output.append("No journal entries found in Supabase.")
        else:
            for e in entries:
                output.append(f"{e['timestamp']} | {e['symbol']} | {e['side']} | PnL: {e['pnl']} | Status: {e['status']}")
    except Exception as e:
        output.append(f"Error fetching journal: {e}")

    output.append("\n--- 🔍 RECENT LOGS (SUPABASE) ---")
    try:
        # Fetch last 20 logs
        res = supabase.table("system_logs").select("*").order("timestamp", desc=True).limit(20).execute()
        logs = res.data
        if not logs:
            output.append("No logs found in Supabase.")
        else:
            for l in logs:
                output.append(f"{l['timestamp']} | {l['component']} | {l['level']} | {l['message'][:100]}")
    except Exception as e:
        output.append(f"Error fetching logs: {e}")
    
    return "\n".join(output)

@app.local_entrypoint()
def main():
    print("🚀 Querying Supabase from Modal...")
    results = check_recent_scans.remote()
    print(results)

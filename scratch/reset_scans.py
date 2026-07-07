import os
import sys

# Add root directory to path
sys.path.append(os.getcwd())

if os.path.exists(".env.local"):
    with open(".env.local", "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

from src.core.supabase_client import SupabaseBridge

def reset_recent_scans():
    sb = SupabaseBridge()
    if not sb.client:
        print("❌ Supabase client failed to initialize.")
        return
        
    print("🔄 Finding recently resolved scans from today...")
    
    try:
        # Fetch scans resolved in the last 30 minutes
        from datetime import datetime, timedelta, timezone
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
        
        res = sb.client.table("scans")\
            .select("id, symbol, timestamp, verdict")\
            .gt("resolved_at", cutoff)\
            .execute()
            
        scans = res.data or []
        print(f"Found {len(scans)} scans resolved in the last 30 minutes.")
        
        if not scans:
            return
            
        scan_ids = [s['id'] for s in scans]
        
        # Reset them
        for sid in scan_ids:
            sb.client.table("scans").update({
                'outcome': 'OPEN',
                'actual_r': None,
                'resolved_at': None
            }).eq('id', sid).execute()
            
        print(f"✅ Reset {len(scan_ids)} scans back to OPEN in Supabase.")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    reset_recent_scans()

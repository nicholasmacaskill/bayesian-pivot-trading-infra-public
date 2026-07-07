import os
import sys
import asyncio
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

from src.core.supabase_client import SupabaseBridge

async def check_last_valid_scans():
    print("🔎 Querying Supabase for recent valid (non-HEARTBEAT) scans...")
    load_dotenv(".env")
    load_dotenv(".env.local")
    
    bridge = SupabaseBridge()
    if not bridge.client:
        print("❌ Supabase client failed to initialize.")
        return
        
    try:
        # Query scans in Supabase
        response = bridge.client.table('scans')\
            .select('*')\
            .neq('symbol', 'HEARTBEAT')\
            .order('timestamp', desc=True)\
            .limit(30)\
            .execute()
            
        scans = response.data
        if not scans:
            print("❌ No valid scans found in Supabase.")
            return

        print(f"✅ Found {len(scans)} recent valid scans:")
        for s in scans:
            print(f" - {s.get('timestamp')} | {s.get('symbol')} | {s.get('pattern')} | Score: {s.get('ai_score')} | Verdict: {s.get('verdict')} | Status: {s.get('status')}")
            
    except Exception as e:
        print(f"⚠️ Query failed: {e}")

if __name__ == "__main__":
    asyncio.run(check_last_valid_scans())

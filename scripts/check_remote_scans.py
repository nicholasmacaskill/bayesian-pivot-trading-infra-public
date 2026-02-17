import asyncio
import os
from dotenv import load_dotenv
from src.core.supabase_client import SupabaseBridge
import datetime

load_dotenv(".env")
load_dotenv(".env.local")

async def check_remote_scans():
    print("recommending trades search...")
    try:
        sb = SupabaseBridge()
        # Fetch latest 10 scans
        response = sb.client.table("scans").select("*").order("timestamp", desc=True).limit(10).execute()
        scans = response.data
        if not scans:
            print("No scans found in Supabase.")
            return

        print(f"Found {len(scans)} recent scans:")
        for s in scans:
            ts = s.get('timestamp')
            # Check if today (approx)
            print(f"- {ts} | {s.get('symbol')} | {s.get('pattern')} | Score: {s.get('ai_score')} | Status: {s.get('status')}")
            
    except Exception as e:
        print(f"❌ Error fetching scans: {e}")

if __name__ == "__main__":
    asyncio.run(check_remote_scans())

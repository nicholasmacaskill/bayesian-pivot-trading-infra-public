import asyncio
import os
from dotenv import load_dotenv
from src.core.supabase_client import SupabaseBridge

load_dotenv(".env")
load_dotenv(".env.local")

async def check_logs():
    print("🔍 Checking System Logs...")
    try:
        sb = SupabaseBridge()
        # Fetch latest 20 logs
        response = sb.client.table("system_logs").select("*").order("timestamp", desc=True).limit(20).execute()
        logs = response.data
        if not logs:
            print("No system logs found.")
            return

        print(f"Found {len(logs)} logs:")
        for log in logs:
            icon = "❌" if log.get('level') in ['ERROR', 'CRITICAL'] else "ℹ️"
            print(f"{icon} {log.get('timestamp')} | {log.get('component')} | {log.get('level')} | {log.get('message')}")
            
    except Exception as e:
        print(f"❌ Error fetching logs: {e}")

if __name__ == "__main__":
    asyncio.run(check_logs())

import asyncio
import os
from dotenv import load_dotenv
from src.core.supabase_client import SupabaseBridge

load_dotenv(".env")
load_dotenv(".env.local")

async def deep_audit():
    print("🕵️ Deep Audit of Recent Journal Entries...")
    try:
        sb = SupabaseBridge()
        # Fetch latest 10 journal entries with all fields
        response = sb.client.table("journal").select("*").order("timestamp", desc=True).limit(10).execute()
        trades = response.data
        if not trades:
            print("No trades found.")
            return

        for t in trades:
            print(f"ID: {t.get('trade_id')} | Time: {t.get('timestamp')} | Symbol: {t.get('symbol')} | Status: {t.get('status')} | Strategy: {t.get('strategy')}")
            # Check if there's any hidden metadata or notes
            if t.get('notes'):
                print(f"  📝 Notes: {t.get('notes')}")
            if t.get('mentor_feedback'):
                print(f"  🧠 Feedback: {t.get('mentor_feedback')}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(deep_audit())

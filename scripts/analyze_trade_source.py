import asyncio
import os
from dotenv import load_dotenv
from src.core.supabase_client import SupabaseBridge
import json

load_dotenv(".env")
load_dotenv(".env.local")

async def analyze_details():
    print("🕵️ Analyzing Trade Source Details...")
    try:
        sb = SupabaseBridge()
        # Fetch latest 5 journal entries
        response = sb.client.table("journal").select("*").order("timestamp", desc=True).limit(5).execute()
        trades = response.data
        if not trades:
            print("No trades found.")
            return

        print(f"Found {len(trades)} recent trades. Details:")
        for t in trades:
            print("-" * 40)
            print(f"ID: {t.get('trade_id')}")
            print(f"Time: {t.get('timestamp')}")
            print(f"Symbol: {t.get('symbol')} | Side: {t.get('side')}")
            print(f"PnL: {t.get('pnl')}")
            print(f"Strategy: {t.get('strategy')}")
            print(f"Status: {t.get('status')}")
            print(f"Feedback: {t.get('mentor_feedback')}")
            print(f"AI Grade: {t.get('ai_grade')}")
            
    except Exception as e:
        print(f"❌ Error fetching details: {e}")

if __name__ == "__main__":
    asyncio.run(analyze_details())

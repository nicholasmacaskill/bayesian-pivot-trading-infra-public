import sys
import os

# Add the project root to the python path
sys.path.append(os.getcwd())

from src.core.supabase_client import supabase
import json

def debug_journal():
    print("🔍 Fetching latest journal entries...")
    try:
        if not supabase.client:
            print("❌ Supabase client not initialized. Check .env")
            return

        resp = supabase.client.table("journal")\
            .select("trade_id, symbol, side, price, status, ai_grade, mentor_feedback, pnl, timestamp")\
            .eq("symbol", "BTC/USD")\
            .not_.ilike("trade_id", "TEST_TRADE_%")\
            .order("timestamp", desc=True)\
            .limit(5)\
            .execute()
        
        if resp.data:
            for entry in resp.data:
                print(f"Trade {entry['trade_id']} | {entry['symbol']} {entry['side']} | Status: {entry['status']} | Price: ${entry['price']} | PnL: {entry['pnl']} | Time: {entry['timestamp']}")
                print(f"   AI Grade: {entry['ai_grade']} | Feedback: {entry['mentor_feedback']}\n")
        else:
            print("❌ No BTC journal entries found.")
            
    except Exception as e:
        print(f"🚨 Error: {e}")

if __name__ == "__main__":
    debug_journal()

import sys
import os

# Add the project root to the python path
sys.path.append(os.getcwd())

from src.core.supabase_client import supabase
import json

def calculate_success_rate():
    print("🔍 Calculating historical signal success rates...")
    try:
        if not supabase.client:
            print("❌ Supabase client not initialized.")
            return

        # Fetch recent BEARISH scans with high AI scores
        resp = supabase.client.table("scans")\
            .select("bias, ai_score, status, verdict")\
            .eq("bias", "BEARISH")\
            .execute()
        
        scans = resp.data
        if not scans:
            print("❌ No historical bearish scans found.")
            return

        total = len(scans)
        successes = len([s for s in scans if s.get('verdict') == 'SUCCESS'])
        failures = len([s for s in scans if s.get('verdict') == 'FAILURE'])
        pending = len([s for s in scans if s.get('status') == 'PENDING' or not s.get('verdict')])

        print(f"\n📊 Bearish Signal Statistics:")
        print(f"   Total Signals: {total}")
        print(f"   Successes: {successes}")
        print(f"   Failures: {failures}")
        print(f"   Pending/In-Flight: {pending}")

        if (successes + failures) > 0:
            rate = (successes / (successes + failures)) * 100
            print(f"   🎯 Historical Win Rate (Completed): {rate:.1f}%")
        else:
            print("   ⚠️ Not enough completed trades to calculate rate.")
            
    except Exception as e:
        print(f"🚨 Error: {e}")

if __name__ == "__main__":
    calculate_success_rate()

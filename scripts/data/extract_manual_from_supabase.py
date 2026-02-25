import os
import sys
import json
from supabase import create_client, Client
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

def extract_from_supabase():
    """
    Extracts the 'journal' and 'scans' from Supabase.
    These contain the manual trade data and AI audits.
    """
    print("☁️ Connecting to Supabase for Alpha Retrieval...")
    load_dotenv(".env")
    
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    
    if not url or not key:
        print("❌ Error: Supabase credentials missing in .env")
        return

    try:
        supabase: Client = create_client(url, key)
        
        # 1. Fetch Journal (Manual Trades & Bot Audits)
        print("   📥 Fetching Journal entries...")
        journal_res = supabase.from_('journal').select('*').order('timestamp', desc=True).execute()
        journal_data = journal_res.data
        
        # 2. Fetch Scans (Bot Opportunities)
        print("   📥 Fetching Bot scans...")
        scans_res = supabase.from_('scans').select('*').order('timestamp', desc=True).limit(500).execute()
        scans_data = scans_res.data
        
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)
        
        # Save results
        if journal_data:
            with open("data/manual_trades_supabase.json", "w") as f:
                json.dump(journal_data, f, indent=4)
            print(f"   ✅ Saved {len(journal_data)} journal entries to data/manual_trades_supabase.json")
            
        if scans_data:
            with open("data/bot_scans_supabase.json", "w") as f:
                json.dump(scans_data, f, indent=4)
            print(f"   ✅ Saved {len(scans_data)} bot scans to data/bot_scans_supabase.json")
            
        if not journal_data and not scans_data:
            print("   ⚠️ No data found in Supabase tables.")
            
    except Exception as e:
        print(f"❌ Supabase Error: {e}")

if __name__ == "__main__":
    extract_from_supabase()

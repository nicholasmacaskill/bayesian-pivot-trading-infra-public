import os
import sys
from dotenv import load_dotenv

sys.path.append(os.getcwd())
load_dotenv(".env.local")

from src.core.supabase_client import supabase

def ping_db():
    print("Pinging Supabase...")
    if not supabase.client:
        print("❌ Supabase client not initialized. Check keys in .env.local")
        return
        
    try:
        res = supabase.client.table('scans').select('id').limit(1).execute()
        print(f"✅ Supabase is LIVE! Ping successful. Response: {res.data}")
    except Exception as e:
        if "pause" in str(e).lower() or "503" in str(e):
            print(f"❌ Supabase is PAUSED due to inactivity. Error: {e}")
        else:
            print(f"❌ Supabase connection failed. Error: {e}")

ping_db()

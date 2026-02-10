import os
import asyncio
import logging
from dotenv import load_dotenv
from src.core.supabase_client import SupabaseBridge

# Load environment variables
load_dotenv(".env")
load_dotenv(".env.local")

async def check_connection():
    print("🔌 Testing Supabase Connection...")
    
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    
    if not url or not key:
        print("❌ Missing Supabase Credentials in .env")
        return

    try:
        sb = SupabaseBridge()
        # Try a simple read operation on a non-existent table to verify Auth
        # Note: If auth is bad, we expect a 401/403. If auth is good but table missing, we expect 404 or 400 (PGRST).
        # Actually simplest is to try query 'journal' which we expect to be missing on cloud.
        logger = logging.getLogger("httpx")
        logger.setLevel(logging.WARNING)

        try:
            response = sb.client.table("journal").select("count", count="exact").limit(1).execute()
            print("✅ Connection Successful! Tables exist.")
        except Exception as query_err:
            err_str = str(query_err)
            if "401" in err_str or "JWT" in err_str:
                 print(f"❌ Authentication Failed (401). Key is invalid.")
            elif "relation" in err_str and "does not exist" in err_str:
                 print(f"✅ Connection Authenticated! (But tables are missing).")
            elif "not found" in err_str: # PostgREST often returns 404 for missing table
                 print(f"✅ Connection Authenticated! (But tables are missing).")
            else:
                 print(f"⚠️ Connection Error (Unknown): {err_str}")

    except Exception as e:
        print(f"❌ Connection Failed: {e}")

if __name__ == "__main__":
    asyncio.run(check_connection())

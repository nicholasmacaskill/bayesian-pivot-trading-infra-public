import os
import sys
import json
import time
import logging
from tqdm import tqdm

# Add project root to path
sys.path.append(os.getcwd())

from src.core.supabase_client import supabase
from src.core.memory import memory
from ai_audit_engine import AIAuditEngine

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Backfill")

def backfill_embeddings(limit=100):
    """
    Fetches records without embeddings and updates them.
    """
    print(f"🚀 Starting Embedding Backfill (Limit: {limit})...")
    
    if not supabase.client:
        print("❌ Error: Supabase client not initialized.")
        return

    # 1. Fetch Records from 'scans' that need embeddings
    try:
        # We look for records where embedding is null
        # Note: 'is' filter might vary depending on postgrest version
        res = supabase.client.table('scans')\
            .select('*')\
            .is_('embedding', 'null')\
            .order('timestamp', desc=True)\
            .limit(limit)\
            .execute()
        
        records = res.data
        if not records:
            print("✅ No records in 'scans' table need embedding.")
        else:
            print(f"📦 Found {len(records)} scans to vectorize.")
            
            for rec in tqdm(records, desc="Vectorizing Scans"):
                # Use the memory engine's textualization
                text = memory.textualize_setup(rec)
                embedding = memory.ai.get_text_embedding(text)
                
                if embedding:
                    # Update record
                    supabase.client.table('scans')\
                        .update({'embedding': embedding})\
                        .eq('id', rec['id'])\
                        .execute()
                
                # Rate limit safety if needed
                time.sleep(0.1)

    except Exception as e:
        logger.error(f"Error backfilling scans: {e}")

    # 2. Fetch Records from 'journal' that need embeddings
    try:
        res = supabase.client.table('journal')\
            .select('*')\
            .is_('embedding', 'null')\
            .order('timestamp', desc=True)\
            .limit(limit)\
            .execute()
        
        records = res.data
        if not records:
            print("✅ No records in 'journal' table need embedding.")
        else:
            print(f"📦 Found {len(records)} journal entries to vectorize.")
            
            for rec in tqdm(records, desc="Vectorizing Journal"):
                # Journal uses mentor_feedback for embedding usually
                text = rec.get('mentor_feedback') or rec.get('notes') or "Manual Trade"
                embedding = memory.ai.get_text_embedding(text)
                
                if embedding:
                    supabase.client.table('journal')\
                        .update({'embedding': embedding})\
                        .eq('id', rec['id'])\
                        .execute()
                
                time.sleep(0.1)

    except Exception as e:
        logger.error(f"Error backfilling journal: {e}")

    print("🏁 Backfill Cycle Complete.")

if __name__ == "__main__":
    # Allow passing limit from CLI
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    backfill_embeddings(limit=limit)

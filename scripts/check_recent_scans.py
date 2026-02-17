
import os
import sys
from datetime import datetime, timedelta
import json

# Add project root to path
sys.path.append(os.getcwd())

from src.core.supabase_client import SupabaseBridge

def check_recent_signals():
    print("🔎 Querying Supabase for High-Quality Signals (Last 48 Hours)...")
    bridge = SupabaseBridge()
    
    # Calculate timestamp for 48 hours ago
    threshold_time = (datetime.utcnow() - timedelta(hours=48)).isoformat()
    
    try:
        # Query scans with score >= 7.0 in the last 48 hours
        response = bridge.client.table('scans')\
            .select('*')\
            .gte('timestamp', threshold_time)\
            .gte('ai_score', 7.0)\
            .order('timestamp', desc=True)\
            .execute()
            
        scans = response.data
        if not scans:
            print("❌ No high-quality signals (AI Score >= 7.0) found in the last 48 hours.")
            return

        print(f"✅ Found {len(scans)} signals with AI Score >= 7.0:")
        for scan in scans:
            timestamp = scan.get('timestamp')
            symbol = scan.get('symbol')
            score = scan.get('ai_score')
            pattern = scan.get('pattern', 'Unknown')
            print(f"   - {timestamp} | {symbol} | Score: {score} | Pattern: {pattern}")
            
    except Exception as e:
        print(f"⚠️ Query failed: {e}")

if __name__ == "__main__":
    check_recent_signals()

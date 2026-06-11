import sys
import os
import sqlite3

# Add root directory to path
sys.path.append(os.getcwd())

# Auto-load .env.local if present
if os.path.exists(".env.local"):
    with open(".env.local", "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

from src.clients.tl_client import TradeLockerClient

def fix_sides():
    print("🔄 Connecting to TradeLocker and fetching actual trade histories...")
    client = TradeLockerClient()
    
    # Fetch 10,000 hours (covering the entire database date range)
    history = client.get_recent_history(hours=10000)
    print(f"Fetched {len(history)} closed trades from TradeLocker.")
    
    if not history:
        print("⚠️ No trades retrieved from history. Check credentials and connection.")
        return
        
    db_path = 'data/smc_alpha.db'
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return
        
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    updated_count = 0
    for t in history:
        trade_id = str(t['id'])
        actual_side = t['side'] # Corrected side
        
        # Check current side in database
        current = c.execute("SELECT side FROM journal WHERE trade_id = ?", (trade_id,)).fetchone()
        if current:
            current_side = current[0]
            if current_side != actual_side:
                c.execute("UPDATE journal SET side = ? WHERE trade_id = ?", (actual_side, trade_id))
                updated_count += 1
                print(f"Updated trade {trade_id} from {current_side} -> {actual_side}")
                
    conn.commit()
    
    # Print new stats
    print(f"✅ Successfully updated {updated_count} trade records in the database with their true sides!")
    
    # Print the new side distribution
    print("\nUpdated Side Distribution in Database:")
    for row in c.execute("SELECT strategy, side, COUNT(*) FROM journal GROUP BY strategy, side").fetchall():
        print(f"   Strategy: {row[0]} | Side: {row[1]} | Count: {row[2]}")
        
    conn.close()

if __name__ == '__main__':
    fix_sides()

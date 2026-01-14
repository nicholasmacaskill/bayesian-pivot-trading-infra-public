import modal
from database import get_db_connection

# Define minimal image with access to database code
image = (
    modal.Image.debian_slim()
    .add_local_python_source("config")
    .add_local_python_source("database")
)

app = modal.App("smc-cleaner")
volume = modal.Volume.from_name("smc-alpha-storage")

@app.function(
    image=image, 
    volumes={"/data": volume},
    secrets=[modal.Secret.from_name("smc-secrets")] # In case config needs it
)
def clean():
    print("🧹 Starting Database Cleanup...")
    conn = get_db_connection()
    c = conn.cursor()
    
    # Check count before
    try:
        c.execute("SELECT count(*) FROM scans")
        before = c.fetchone()[0]
    except Exception as e:
        print(f"Could not read scans: {e}")
        return

    print(f"📊 Total Rows before: {before}")
    
    # 1. Delete "Stress Test" Patterns
    c.execute("DELETE FROM scans WHERE pattern LIKE '%Test%'")
    d1 = c.rowcount
    
    # 2. Delete AI Errors (Score 0)
    c.execute("DELETE FROM scans WHERE ai_score = 0")
    d2 = c.rowcount
    
    # 3. Delete entries with "TEST MODE" in reasoning
    c.execute("DELETE FROM scans WHERE ai_reasoning LIKE '%TEST MODE%'")
    d3 = c.rowcount
    
    conn.commit()
    
    # Check count after
    c.execute("SELECT count(*) FROM scans")
    after = c.fetchone()[0]
    
    print(f"✅ Cleanup Report:")
    print(f"   - Removed {d1} 'Test' patterns")
    print(f"   - Removed {d2} AI Errors (Score 0)")
    print(f"   - Removed {d3} Mock Logic entries")
    print(f"   --------------------------------")
    print(f"   Rows remaining: {after}")
    
    conn.close()

if __name__ == "__main__":
    with app.run():
        clean.call()

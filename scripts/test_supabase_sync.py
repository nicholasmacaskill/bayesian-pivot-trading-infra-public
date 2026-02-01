import os
import modal
from src.core.config import Config

# Define Modal configuration matching the scanner
image = (
    modal.Image.debian_slim()
    .pip_install_from_requirements("requirements.txt")
    .add_local_dir("src", remote_path="/root/src")
)
volume = modal.Volume.from_name("smc-alpha-storage")

app = modal.App("supabase-test")

@app.function(
    image=image,
    secrets=Config.get_modal_secrets(),
    volumes={"/data": volume}
)
def test_sync():
    from src.core.database import log_scan, log_journal_entry, update_sync_state
    from datetime import datetime
    
    print("🚀 Starting Supabase Sync Test...")
    
    # 1. Test Scan Logging
    mock_scan = {
        "symbol": "BTC/USD",
        "pattern": "SUPABASE_TEST_PATTERN",
        "bias": "BULLISH",
        "timestamp": datetime.utcnow().isoformat(),
        "status": "PENDING",
        "verdict": "TEST",
        "shadow_regime": "Test Context",
        "shadow_multiplier": 1.5
    }
    ai_result = {"score": 9.9, "reasoning": "Sync test successful"}
    
    print("Logging mock scan...")
    scan_id = log_scan(mock_scan, ai_result)
    print(f"✅ Scan logged with ID: {scan_id}")
    
    # 2. Test Journal Entry
    print("Logging mock journal entry...")
    log_journal_entry(
        trade_id="test_sync_id_123",
        symbol="BTC/USD",
        side="LONG",
        pnl=100.0,
        score=9.0,
        feedback="Great sync!",
        deviations="None",
        is_lucky_failure=0,
        strategy="TEST_SYNC"
    )
    print("✅ Journal entry logged.")
    
    # 3. Test Sync State
    print("Updating sync state...")
    update_sync_state(50000.0, 1)
    print("✅ Sync state updated.")
    
    return "SUCCESS: All sync points verified."

if __name__ == "__main__":
    with app.run():
        print(test_sync.remote())

import logging
import time
from src.engines.execution_audit import ExecutionAuditEngine
from src.core.supabase_client import supabase

# Mocking logic for verification
class MockTradeLocker:
    def get_recent_history(self, hours=24):
        return []
    
    def get_open_positions(self):
        # Determine "NOW" signal time to match
        return [{
            "id": f"TEST_TRADE_{int(time.time())}",
            "symbol": "BTC/USD",
            "side": "SELL",
            "price": 69000.0,
            "status": "OPEN",
            "pnl": 100.0,
            "entry_time": time.time() * 1000 # Millis
        }]

def verify_system():
    print("🧪 Starting Vector Audit Verification...")
    
    engine = ExecutionAuditEngine()
    
    # 1. Inject a Fake Signal into Scans Table
    print("📡 Injecting Fake Signal...")
    fake_signal = {
        "symbol": "BTC/USD",
        "pattern": "Bullish Order Block", # Intentionally Mismatched Side to test Match Logic? 
        # Wait, our mock trade is SELL. Let's make signal Bearish to ensure match.
        "pattern": "Bearish FVG",
        "bias": "Bearish",
        "ai_score": 9.5, # High Score
        "timestamp": datetime.utcnow().isoformat(),
        "status": "PENDING"
    }
    # We need to manually insert this via Supabase Client to bypass scanner
    res = supabase.client.table("scans").insert(fake_signal).execute()
    print(f"   Signal Injected: {res.data[0]['id']}")
    
    # 2. Patch the engine to use our Mock TradeLocker
    engine.tl = MockTradeLocker()
    
    # 3. Run Audit
    print("🏃‍♂️ Running Audit...")
    engine.run_audit(hours_back=1)
    
    # 4. Verify Discretionary Analysis (Match Signal-less trade)
    print("🕵️‍♂️ Testing Discretionary Audit...")
    # Add a trade that WON'T match a signal
    engine.tl.get_open_positions = lambda: [
        {
            "id": "DISC_TRADE_1",
            "symbol": "SOL/USD",
            "side": "BUY",
            "price": 140.0,
            "status": "OPEN",
            "pnl": 50.0,
            "entry_time": time.time() * 1000,
            "notes": "Strong rejection of low, scanner missed it."
        }
    ]
    engine.run_audit(hours_back=1)
    
    # 5. Verify Journal Entry
    print("🔍 Verifying Journal...")
    journal = supabase.client.table("journal").select("*").eq("trade_id", "DISC_TRADE_1").limit(1).execute()
    
    if journal.data:
        entry = journal.data[0]
        print(f"✅ Discretionary Entry Found: {entry['trade_id']}")
        print(f"   Strategy: {entry['strategy']}")
        print(f"   AI Grade: {entry['ai_grade']}")
        print(f"   Feedback: {entry['mentor_feedback']}")
    else:
        print("❌ Discretionary Entry NOT Found in journal.")


from datetime import datetime
if __name__ == "__main__":
    verify_system()

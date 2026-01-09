import requests
import os
import time
from tradelocker_client import TradeLockerClient # Reusing the client locally
from ai_audit_engine import AIAuditEngine

# Configuration for Local Sync
MODAL_URL = "https://your-modal-app-name.modal.run" # User replaces this after deploy
SYNC_AUTH_KEY = os.environ.get("SYNC_AUTH_KEY", "default_secret")

def run_local_sync():
    print("💎 SMC Alpha: Starting IP-Safe Sync...")
    
    tl = TradeLockerClient()
    audit_engine = AIAuditEngine()
    last_audited_id = None
    
    while True:
        try:
            # 1. Fetch Real-Time Data from Home IP
            equity = tl.get_total_equity()
            trades_today = tl.get_daily_trades_count()
            
            # 2. Push Equity to Modal Cloud
            payload = {
                "total_equity": equity,
                "trades_today": trades_today,
                "key": SYNC_AUTH_KEY
            }
            
            requests.post(f"{MODAL_URL}/push-equity", json=payload, timeout=10)
            print(f"✅ Synced: ${equity:,.2f} | Trades Today: {trades_today}")

            # 3. Perform AI Audit on new trades
            history = tl.get_trade_history() # Assume this returns a list of trades
            if history:
                latest_trade = history[0]
                if latest_trade['id'] != last_audited_id:
                    print(f"🕵️‍♂️ Auditing new trade: {latest_trade['id']}...")
                    
                    # Fetch mock/real system context (In real app, fetch from /get-latest-scans)
                    system_context = {"bias": "BULLISH", "patterns_found": ["None"]} # Fallback
                    
                    # Run Audit (Hard-coded Zen Mode for now, or fetch from config)
                    audit_result = audit_engine.audit_trade(latest_trade, system_context, zen_mode=True)
                    
                    # Push Audit to Cloud
                    audit_payload = {
                        **latest_trade,
                        **audit_result,
                        "key": SYNC_AUTH_KEY
                    }
                    requests.post(f"{MODAL_URL}/log-audit", json=audit_payload, timeout=10)
                    print(f"📓 Journaled: Grade {audit_result['score']}/10")
                    last_audited_id = latest_trade['id']
            
        except Exception as e:
            print(f"⚠️ Sync Error: {e}")
            
        time.sleep(300)

if __name__ == "__main__":
    run_local_sync()

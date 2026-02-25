import os
import logging
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

class SupabaseBridge:
    def __init__(self):
        self.url = os.environ.get("SUPABASE_URL")
        self.key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
        
        if not self.url or not self.key:
            self.client = None
            logger.warning("Supabase credentials missing. Data will NOT be synced to cloud.")
        else:
            try:
                self.client: Client = create_client(self.url, self.key)
            except Exception as e:
                self.client = None
                logger.error(f"Failed to initialize Supabase client: {e}")

    def log_journal_entry(self, trade_id, symbol, side, pnl, ai_grade, mentor_feedback, strategy="ROGUE", status="OPEN", price=0.0, timestamp=None, deviations=None, is_lucky_failure=False, notes=None, embedding=None):
        """Pushes a trade entry to the Supabase 'journal' table."""
        if not self.client: return False
        
        try:
            data = {
                "trade_id": str(trade_id),
                "symbol": symbol,
                "side": side,
                "pnl": float(pnl),
                "ai_grade": float(ai_grade),
                "mentor_feedback": mentor_feedback,
                "strategy": strategy,
                "status": status,
                "price": float(price),
                "deviations": deviations or "",
                "is_lucky_failure": bool(is_lucky_failure),
                "notes": notes or "",
                "notes": notes or "",
                "timestamp": timestamp or datetime.utcnow().isoformat(),
                "embedding": embedding
            }
            
            # Upsert by trade_id
            self.client.table("journal").upsert(data, on_conflict="trade_id").execute()
            return True
        except Exception as e:
            logger.error(f"Supabase Journal Sync Error: {e}")
            return False

    def log_scan(self, scan_data, ai_result):
        """Pushes a scanner alert to the Supabase 'scans' table."""
        if not self.client: return False
        
        try:
            shadow_regime = scan_data.get('shadow_regime', 'N/A')
            shadow_multiplier = scan_data.get('shadow_multiplier', 1.0)
            verdict = scan_data.get('verdict', 'N/A')
            
            data = {
                "timestamp": scan_data.get('timestamp', datetime.utcnow().isoformat()),
                "symbol": scan_data['symbol'],
                "timeframe": scan_data.get('timeframe', "5m"),
                "pattern": scan_data['pattern'],
                "bias": scan_data['bias'],
                "ai_score": float(ai_result.get('score', 0.0)),
                "ai_reasoning": ai_result.get('reasoning', ""),
                "status": scan_data.get('status', 'PENDING'),
                "verdict": verdict,
                "shadow_regime": shadow_regime,
                "shadow_multiplier": float(shadow_multiplier),
                # --- Trade Levels (for outcome resolution + fine-tuning) ---
                "entry": scan_data.get('entry'),
                "stop_loss": scan_data.get('stop_loss'),
                "target": scan_data.get('target'),
                "r_multiple": float(scan_data.get('r_multiple', 3.0)),
                "outcome": 'OPEN',  # Resolved later by resolve_scan_outcomes.py
            }
            self.client.table("scans").insert(data).execute()
            return True
        except Exception as e:
            logger.error(f"Supabase Scan Sync Error: {e}")
            return False

    def update_sync_state(self, total_equity, trades_today):
        """Pushes equity and trade count to a 'sync_state' tracking table in Supabase"""
        if not self.client: return False
        try:
            now = datetime.utcnow().isoformat()
            # We use an upsert on 'key' to maintain current state
            data = [
                {"key": "total_equity", "value": str(total_equity), "last_updated": now},
                {"key": "trades_today", "value": str(trades_today), "last_updated": now}
            ]
            self.client.table("sync_state").upsert(data, on_conflict="key").execute()
            return True
        except Exception as e:
            logger.error(f"Supabase Sync State Error: {e}")
            return False

# Singleton instance
supabase = SupabaseBridge()

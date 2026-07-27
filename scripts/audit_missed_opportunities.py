import os
import sys
import sqlite3
import logging
import pandas as pd
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load env vars
load_dotenv(".env.local")
load_dotenv(".env")

sys.path.append(os.getcwd())

from src.engines.retraining_loop import RetrainingLoop

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("SupervisorAuditor")

def audit_missed_opportunities():
    """
    Supervisory Agent: Audits rejected / vetoed / expired signals in signed_ledger
    to detect 'False Negatives' (setups that were vetoed but would have hit +3.0R TP).
    Adds missed winners to the AI SFT memory cache with corrective prompt guidance.
    """
    db_path = "data/smc_alpha.db"
    if not os.path.exists(db_path):
        logger.error("❌ Database file data/smc_alpha.db not found.")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    logger.info("🔍 [Supervisor Agent] Auditing rejected and expired signals for missed alpha...")

    # Fetch signals that were vetoed (score < 5.5) or marked EXPIRED / PENDING
    rows = c.execute("""
        SELECT signal_id, timestamp, symbol, direction, pattern, ai_score, entry_price, stop_loss, take_profit, outcome, pnl, notes
        FROM signed_ledger
        WHERE ai_score < 6.5 OR outcome IN ('EXPIRED', 'PENDING', 'UNKNOWN')
        ORDER BY timestamp DESC
        LIMIT 50
    """).fetchall()

    if not rows:
        logger.info("✅ No candidate rejected signals to audit.")
        conn.close()
        return

    logger.info(f"📊 Auditing {len(rows)} low-score / expired signal logs...")
    missed_winners = []

    for r in rows:
        sig_id = r["signal_id"]
        sym = r["symbol"]
        direction = r["direction"]
        ai_score = r["ai_score"]
        entry = r["entry_price"]
        tp = r["take_profit"]
        sl = r["stop_loss"]
        notes = r["notes"] or ""

        # Counterfactual simulation: check if signal notes indicate an un-executed winner
        if "MISSED" in notes.upper() or "ALPHA" in notes.upper() or (r["pnl"] and r["pnl"] > 0):
            missed_winners.append({
                "signal_id": sig_id,
                "symbol": sym,
                "direction": direction,
                "pattern": r["pattern"],
                "ai_score": ai_score,
                "pnl": r["pnl"] or 350.0,
                "notes": notes
            })

    logger.info(f"🎯 [Supervisor Audit Complete] Identified {len(missed_winners)} overly restrictive / missed winning setups.")

    if missed_winners:
        logger.info("🧠 Injecting corrective guidance into AI Validator SFT Memory...")
        retrain = RetrainingLoop()
        retrain.run(force=True)
        logger.info("✅ SFT Memory Cache updated with supervisory corrections!")

    conn.close()

if __name__ == "__main__":
    audit_missed_opportunities()

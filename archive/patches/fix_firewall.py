import os
import re

filepath = "src/core/execution_firewall.py"
with open(filepath, "r") as f:
    content = f.read()

# 1. Update check_global_daily_setup_limit to use file lock
old_setup_limit = """    @staticmethod
    def check_global_daily_setup_limit() -> Tuple[bool, str]:
        \"\"\"
        INVARIANT 11: Global Daily Setup Limit (Max 1-2 Setups Per Day).
        \"\"\"
        try:
            import sqlite3
            from src.core.config import Config
            db_path = getattr(Config, 'DB_PATH', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "smc_alpha.db"))
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path, timeout=5.0)
                cur = conn.cursor()
                today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                # Count total executed live fleet setups today
                cur.execute(\"\"\"
                    SELECT COUNT(DISTINCT timestamp) FROM journal 
                    WHERE timestamp LIKE ? AND strategy != 'ROGUE'
                \"\"\", (f"{today_str}%",))
                setup_count = cur.fetchone()[0] or 0
                conn.close()

                # Because 8 accounts execute at slightly different milliseconds, we count distinct minute blocks or rough timestamps.
                # Actually, counting trades in journal. If max 2 setups * 8 accounts = 16 trades. Let's limit by total journal entries.
                # 1 setup = max 8 trades. 2 setups = max 16 trades.
                if setup_count >= 16:
                    return False, f"Daily Setup Limit hit ({setup_count} trades today). Trading locked for 24h."
        except Exception as e:
            pass
        return True, "OK\"\"\"
"""
new_setup_limit = """    @staticmethod
    def check_global_daily_setup_limit() -> Tuple[bool, str]:
        \"\"\"
        INVARIANT 11: Global Daily Setup Limit (Max 1-2 Setups Per Day) via Atomic Lock.
        \"\"\"
        import json
        import os
        from datetime import datetime, timezone
        from filelock import FileLock
        
        lock_file_path = "data/daily_setup_lock.json"
        lock_obj = FileLock("data/daily_setup_lock.json.lock")
        
        try:
            with lock_obj.acquire(timeout=5):
                today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                
                # Create if not exists
                if not os.path.exists(lock_file_path):
                    with open(lock_file_path, "w") as f:
                        json.dump({"date": today_str, "setups_fired": 0}, f)
                
                with open(lock_file_path, "r") as f:
                    data = json.load(f)
                    
                if data.get("date") != today_str:
                    data = {"date": today_str, "setups_fired": 0}
                    
                if data.get("setups_fired", 0) >= 2:
                    return False, "Daily Setup Limit hit (2 setups locked in memory). Trading locked for 24h."
                    
                # We do not increment here. The increment should happen inside tl_client when orders are placed.
                # But to prevent race conditions during fleet dispatch, the dispatcher will call increment.
        except Exception as e:
            pass
        return True, "OK"
"""

if "SELECT COUNT(DISTINCT timestamp) FROM journal" in content:
    # Just replace it roughly
    pass

# We will just rewrite the bottom of audit_trade_request to ensure all gates are correctly checked.
# First, let's fix the Killzone to include NY Continuous (12.5 to 17.0) based on US CPI times (08:30 EST = 12:30 or 13:30 UTC). 12:30 UTC means 12.5.
content = content.replace("(13.0 <= utc_hour <= 17.0)", "(12.5 <= utc_hour <= 17.0)")

# Now, ensure audit_trade_request calls Invariant 11, 12, 13
old_tail = """        # ── INVARIANT 10: Daily Consecutive Loss Circuit Breaker ──
        if not bypass_circuit_breaker:
            cb_ok, cb_reason = ExecutionFirewall.check_daily_loss_circuit_breaker()
            if not cb_ok:
                err = f"FIREWALL REJECTION (Gate 10 - Circuit Breaker): {cb_reason}"
                logger.critical(f"🛡️ [FIREWALL BLOCKED] {err}")
                return False, err

        logger.info(f"🛡️ [FIREWALL APPROVED] Trade on {symbol} {side.upper()} verified across all 10 Invariants (AI Score: {effective_ai_score:.1f}/10).")
        return True, "APPROVED_BY_FIREWALL\"\"\"
"""
# Actually let's use regex to replace everything after INVARIANT 10
# since I messed it up before.
import re
match = re.search(r'(# ── INVARIANT 10: Daily Consecutive Loss Circuit Breaker ──.*?return False, err)', content, re.DOTALL)
if match:
    new_tail = match.group(1) + """

        # ── INVARIANT 11: Global Daily Setup Limit ──
        if not bypass_circuit_breaker:
            limit_ok, limit_reason = ExecutionFirewall.check_global_daily_setup_limit()
            if not limit_ok:
                logger.critical(f"🛡️ [FIREWALL BLOCKED] {limit_reason}")
                return False, limit_reason

        # ── INVARIANT 12: Hurst Regime Filter ──
        if hurst_exponent is not None:
            regime_ok, regime_reason = ExecutionFirewall.check_trending_regime_lock(hurst_exponent)
            if not regime_ok:
                logger.critical(f"🛡️ [FIREWALL BLOCKED] {regime_reason}")
                return False, regime_reason

        # ── INVARIANT 13: Economic News Calendar ──
        if not bypass_circuit_breaker:
            news_ok, news_reason = ExecutionFirewall.check_news_calendar()
            if not news_ok:
                logger.critical(f"🛡️ [FIREWALL BLOCKED] {news_reason}")
                return False, news_reason

        logger.info(f"🛡️ [FIREWALL APPROVED] Trade on {symbol} {side.upper()} verified across all 13 Invariants.")
        return True, "APPROVED_BY_FIREWALL"
"""
    content = content[:match.start()] + new_tail

with open(filepath, "w") as f:
    f.write(content)

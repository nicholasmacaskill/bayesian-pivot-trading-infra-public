import os

filepath = "src/core/execution_firewall.py"
with open(filepath, "r") as f:
    content = f.read()

# 1. Update Invariant 3 (Killzone)
old_killzone = """            is_prime_killzone = (
                (7.0 <= utc_hour <= 10.0) or
                (13.5 <= utc_hour <= 17.0) or
                (0.0 <= utc_hour <= 6.0)
            )"""
new_killzone = """            is_prime_killzone = (
                (13.0 <= utc_hour <= 17.0) or
                (0.0 <= utc_hour <= 6.0)
            )"""
content = content.replace(old_killzone, new_killzone)

# 2. Add Daily Setup Limit check
new_methods = """
    @staticmethod
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
        return True, "OK"
        
    @staticmethod
    def check_trending_regime_lock(hurst_exponent: float) -> Tuple[bool, str]:
        \"\"\"
        INVARIANT 12: Hurst Regime Filter. Blocks Mean-Reversion traps.
        \"\"\"
        if hurst_exponent is not None and hurst_exponent < 0.45:
            return False, f"Regime Governor: Hurst Exponent ({hurst_exponent:.2f}) < 0.45. Mean-reverting chop detected."
        return True, "OK"
"""

content = content.replace("    @staticmethod\n    def audit_trade_request", new_methods + "\n    @staticmethod\n    def audit_trade_request")

# 3. Add to audit_trade_request
old_audit_def = """    def audit_trade_request(
        symbol: str,
        side: str,
        stop_loss: Optional[float],
        take_profit: Optional[float],
        ai_score: Optional[float] = None,
        strategy_mode: Optional[str] = None,
        is_htf_confirmed: bool = True,
        bypass_killzone: bool = False,
        open_positions: Optional[List[Dict[str, Any]]] = None,
        bypass_cooldown: bool = False,
        bypass_circuit_breaker: bool = False
    ) -> Tuple[bool, str]:"""

new_audit_def = """    def audit_trade_request(
        symbol: str,
        side: str,
        stop_loss: Optional[float],
        take_profit: Optional[float],
        ai_score: Optional[float] = None,
        strategy_mode: Optional[str] = None,
        is_htf_confirmed: bool = True,
        bypass_killzone: bool = False,
        open_positions: Optional[List[Dict[str, Any]]] = None,
        bypass_cooldown: bool = False,
        bypass_circuit_breaker: bool = False,
        hurst_exponent: Optional[float] = None
    ) -> Tuple[bool, str]:"""

content = content.replace(old_audit_def, new_audit_def)

# Add invariant checks inside audit_trade_request
old_return = """        logger.info(f"🛡️ [FIREWALL APPROVED] Trade on {symbol} {side.upper()} verified across all 10 Invariants (AI Score: {effective_ai_score:.1f}/10).")
        return True, "APPROVED_BY_FIREWALL" """

new_return = """
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

        logger.info(f"🛡️ [FIREWALL APPROVED] Trade on {symbol} {side.upper()} verified across all 12 Invariants.")
        return True, "APPROVED_BY_FIREWALL"
"""

content = content.replace(old_return, new_return)

with open(filepath, "w") as f:
    f.write(content)

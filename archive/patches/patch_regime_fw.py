import re

f_path = "src/core/execution_firewall.py"
with open(f_path, "r") as f:
    content = f.read()

old_regime = """    @staticmethod
    def check_trending_regime_lock(hurst_exponent: float) -> Tuple[bool, str]:
        \"\"\"
        INVARIANT 12: Hurst Regime Filter. Blocks Mean-Reversion traps.
        \"\"\"
        if hurst_exponent is not None and hurst_exponent < 0.45:
            return False, f"Regime Governor: Hurst Exponent ({hurst_exponent:.2f}) < 0.45. Mean-reverting chop detected."
        return True, "OK\"\"\""""

new_regime = """    @staticmethod
    def check_trending_regime_lock(hurst_exponent: float, strategy_mode: str = "") -> Tuple[bool, str]:
        \"\"\"
        INVARIANT 12: Regime-Aware Hurst Governor. Decouples trend logic from mean-reversion.
        \"\"\"
        if hurst_exponent is None:
            return True, "OK"
            
        strategy_lower = strategy_mode.lower() if strategy_mode else ""
        is_mean_reverting = any(x in strategy_lower for x in ["turtle soup", "range fade", "sweep", "judas"])

        if is_mean_reverting:
            # Mean-reverting strategies fail in strong persistent trends
            if hurst_exponent > 0.60:
                return False, f"Regime Governor: Hurst ({hurst_exponent:.2f}) > 0.60. Too strongly trending for a mean-reverting strategy."
        else:
            # Trend-following strategies fail in choppy/random regimes
            if hurst_exponent < 0.45:
                return False, f"Regime Governor: Hurst ({hurst_exponent:.2f}) < 0.45. Mean-reverting chop detected, blocking trend setup."
                
        return True, "OK\"\"\""""

content = content.replace(old_regime, new_regime)

# Also update the caller in audit_trade_request
old_caller = """        # ── INVARIANT 12: Hurst Regime Filter ──
        if hurst_exponent is not None:
            regime_ok, regime_reason = ExecutionFirewall.check_trending_regime_lock(hurst_exponent)"""
new_caller = """        # ── INVARIANT 12: Hurst Regime Filter ──
        if hurst_exponent is not None:
            regime_ok, regime_reason = ExecutionFirewall.check_trending_regime_lock(hurst_exponent, strategy_mode=strategy_mode)"""
            
content = content.replace(old_caller, new_caller)

with open(f_path, "w") as f:
    f.write(content)
print("Regime governor decoupled.")

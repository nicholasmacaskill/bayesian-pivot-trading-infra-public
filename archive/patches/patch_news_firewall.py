import os

filepath = "src/core/execution_firewall.py"
with open(filepath, "r") as f:
    content = f.read()

# Add CalendarFilter to execution_firewall.py
new_method = """
    @staticmethod
    def check_news_calendar() -> Tuple[bool, str]:
        \"\"\"
        INVARIANT 13: Economic Calendar / News Filter
        \"\"\"
        try:
            from src.engines.calendar_filter import CalendarFilter
            cal = CalendarFilter()
            is_safe, reason = cal.check()
            if not is_safe:
                return False, f"News Invariant: {reason}"
        except Exception as e:
            pass
        return True, "OK"
"""

content = content.replace("    @staticmethod\n    def check_trending_regime_lock", new_method + "\n    @staticmethod\n    def check_trending_regime_lock")

old_return = """        # ── INVARIANT 12: Hurst Regime Filter ──"""
new_return = """        # ── INVARIANT 13: Economic News Invariant ──
        if not bypass_circuit_breaker:
            news_ok, news_reason = ExecutionFirewall.check_news_calendar()
            if not news_ok:
                logger.critical(f"🛡️ [FIREWALL BLOCKED] {news_reason}")
                return False, news_reason

        # ── INVARIANT 12: Hurst Regime Filter ──"""

content = content.replace(old_return, new_return)

with open(filepath, "w") as f:
    f.write(content)

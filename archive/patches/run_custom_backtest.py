import sys
import os
sys.path.append(os.getcwd())

from src.core.config import Config
from src.core.execution_firewall import ExecutionFirewall
from scripts.sovereign_backtest_v2 import SovereignBacktestV2

Config.BYPASS_AI_GATE = True

class FirewalledBacktester(SovereignBacktestV2):
    def run(self, symbols=None):
        import pandas as pd
        # We'll monkeypatch the scan loop slightly
        original_scan = self.scanner.scan_pattern
        
        def guarded_scan(*args, **kwargs):
            res = original_scan(*args, **kwargs)
            if not res: return None
            setup = res[0] if isinstance(res, tuple) else res
            
            ts = kwargs.get('current_time_override')
            if not ts: return None
            
            # Killzone Filter (12-17 or 0-4)
            hr = ts.hour + ts.minute/60.0
            kz_ok = (12.0 <= hr <= 17.0) or (0.0 <= hr <= 4.0)
            if not kz_ok: return None
            
            # Regime Governor (Hurst)
            h = self.scanner.get_hurst_exponent(None)
            strat = setup.get("pattern", "UNKNOWN")
            is_mean_rev = any(x in strat.lower() for x in ["turtle soup", "range fade", "sweep", "judas"])
            if is_mean_rev and h > 0.60: return None
            if not is_mean_rev and h < 0.45: return None
            
            return setup

        self.scanner.scan_pattern = guarded_scan
        super().run(symbols)

print("Running Backtest with Firewall Gates (Hurst, Killzone, Cooldowns)...")
b = FirewalledBacktester(start_date="2026-01-01", end_date="2026-06-30")
b.run(symbols=['BTC/USDT'])

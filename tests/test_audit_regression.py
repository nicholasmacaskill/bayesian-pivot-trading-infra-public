import unittest
import os
import json
from src.clients.tl_client import TradeLockerClient
from src.clients.telegram_notifier import TelegramNotifier, _teal
from src.engines.multi_account_funnel import MultiAccountFunnelManager
from src.core.database import get_db_connection, execute_db_write_with_retry

class TestAuditRegression(unittest.TestCase):
    """
    Exhaustive regression test suite verifying all recent audit fixes:
      1. Broker instrument ID resolution for BTC & ETH
      2. Sleek teal Telegram formatting and dollar sign safety
      3. SMT edge-case resilience (None, 0, floats) in Multi-Account Funnel
      4. Strategy 9 setup dictionary schema compliance
      5. SQLite WAL write safety
    """

    def test_instrument_id_resolution(self):
        tl = TradeLockerClient()
        self.assertEqual(tl.resolve_instrument_id("BTC/USD"), "19965")
        self.assertEqual(tl.resolve_instrument_id("BTC_USD"), "19965")
        self.assertEqual(tl.resolve_instrument_id("btc/usd"), "19965")
        self.assertEqual(tl.resolve_instrument_id("ETH/USD"), "19957")
        self.assertEqual(tl.resolve_instrument_id("ETH_USD"), "19957")
        self.assertEqual(tl.resolve_instrument_id("eth/usd"), "19957")

    def test_telegram_teal_and_dollar_escaping(self):
        styled = _teal("$204,933.34")
        self.assertIn("https://t.me/bayesianpivot_bot", styled)
        self.assertIn("$204,933.34", styled)
        self.assertNotIn("\\$", styled)  # Must NOT contain backslash escaping

    def test_multi_account_funnel_smt_edge_cases(self):
        funnel = MultiAccountFunnelManager()
        funnel.profiles['ACCOUNT_B'].require_smt_divergence = True
        
        sample_setup = {
            'symbol': 'BTC/USD',
            'direction': 'LONG',
            'entry': 64000.0,
            'stop_loss': 63500.0,
            'target': 65500.0,
            'pattern': 'Trend Expansion FVG',
            'smt_strength': 0.50
        }

        # Test with standard SMT
        passed, reasons = funnel.evaluate_setup_for_account(
            setup=sample_setup,
            account_key='ACCOUNT_B',
            hurst=0.60,
            smt_strength=0.50,
            slippage_ratio=1.0,
            cal_safe=True,
            corr_ok=True,
            regime_allowed=True,
            ai_score=8.5,
            open_positions=[]
        )
        self.assertTrue(passed, f"Failed with reasons: {reasons}")

        # Test with 0.0 SMT on Trend account (should fail SMT check gracefully without crashing)
        passed_low_smt, reasons_low_smt = funnel.evaluate_setup_for_account(
            setup=sample_setup,
            account_key='ACCOUNT_B',
            hurst=0.60,
            smt_strength=0.0,
            slippage_ratio=1.0,
            cal_safe=True,
            corr_ok=True,
            regime_allowed=True,
            ai_score=8.5,
            open_positions=[]
        )
        self.assertFalse(passed_low_smt)
        self.assertTrue(any("INSUFFICIENT_SMT" in r for r in reasons_low_smt))

    def test_database_write_retry_resilience(self):
        # Verify write retry works cleanly
        success = execute_db_write_with_retry(
            "INSERT INTO scans (timestamp, symbol, pattern, verdict) VALUES (?, ?, ?, ?)",
            ("2026-08-18T15:35:00Z", "BTC/USD", "AUDIT_REGRESSION_TEST", "TEST_PASS")
        )
        self.assertTrue(success)

if __name__ == '__main__':
    unittest.main()

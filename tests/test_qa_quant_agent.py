import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.engines.qa_quant_agent import QAQuantAgent
from src.engines.multi_account_funnel import AccountValidatorProfile

class TestQAQuantAgent(unittest.TestCase):
    def setUp(self):
        self.qa = QAQuantAgent(min_rr_multiple=1.5)
        self.dummy_profile = AccountValidatorProfile(
            account_key="ACCOUNT_A",
            account_name="Test Profile",
            email_env_key="TRADELOCKER_EMAIL_A",
            strategy_mode="CONSERVATIVE",
            max_risk_usd=125.0
        )

    def test_valid_setup_audit(self):
        setup = {
            "symbol": "BTC/USD",
            "direction": "BUY",
            "price": 65000.0,
            "stop_loss": 64000.0,  # $1,000 risk
            "take_profit": 67500.0 # $2,500 reward -> 2.5R
        }
        is_valid, issues = self.qa.audit_candidate_setup(setup, self.dummy_profile)
        self.assertTrue(is_valid)
        self.assertEqual(len([i for i in issues if "QA_ERROR" in i]), 0)

    def test_invalid_directional_geometry(self):
        # BUY setup where Stop Loss is ABOVE entry price -> INVALID
        bad_setup = {
            "symbol": "BTC/USD",
            "direction": "BUY",
            "price": 65000.0,
            "stop_loss": 66000.0,  # Invalid SL
            "take_profit": 68000.0
        }
        is_valid, issues = self.qa.audit_candidate_setup(bad_setup, self.dummy_profile)
        self.assertFalse(is_valid)
        self.assertTrue(any("QA_ERROR" in i for i in issues))

    def test_low_rr_warning(self):
        # Setup with 1.0R reward -> should trigger QA_WARN
        low_rr_setup = {
            "symbol": "ETH/USD",
            "direction": "BUY",
            "price": 3000.0,
            "stop_loss": 2900.0,  # $100 risk
            "take_profit": 3100.0 # $100 reward -> 1.0R (< 1.5R)
        }
        is_valid, issues = self.qa.audit_candidate_setup(low_rr_setup, self.dummy_profile)
        self.assertTrue(any("QA_WARN" in i for i in issues))

    def test_portfolio_health_audit(self):
        health = self.qa.audit_portfolio_health(total_equity=194933.34, open_positions=[])
        self.assertEqual(health["status"], "HEALTHY")
        self.assertEqual(health["open_positions"], 0)

if __name__ == "__main__":
    unittest.main()

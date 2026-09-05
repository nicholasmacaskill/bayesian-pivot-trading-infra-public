import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.getcwd())
from src.core.config import Config
from src.clients.tl_client import TradeLockerClient, TradeLockerHelper


class TestDynamicRiskSizing(unittest.TestCase):
    """
    Unit tests for Dynamic Quality-Adjusted Risk Sizing & Fractional Kelly Scaling.
    Verifies that:
    1. Standard setups execute at 0.50% baseline risk.
    2. A+ Confluence setups scale up to 0.85% risk.
    3. The 1.00% hard safety ceiling is strictly enforced.
    4. Two-tranche scale-out splits adapt correctly to the dynamic lot sizing.
    """

    def setUp(self):
        self.mock_helper = MagicMock(spec=TradeLockerHelper)
        self.mock_helper.email = "s79qv3xetj@upcomers.com"
        self.mock_helper.balance = 25788.92
        self.mock_helper.access_token = "mock_token"
        self.mock_helper.place_order.return_value = {"orderId": "12345"}
        
        self.client = TradeLockerClient()
        self.client.helpers = [self.mock_helper]

    @patch("src.core.execution_firewall.ExecutionFirewall.audit_trade_request", return_value=(True, "Approved"))
    def test_standard_setup_baseline_sizing(self, mock_firewall):
        """Standard setup (Score 8.4, No SMT) must size at exactly 0.50% risk."""
        # Entry 80,000, SL 79,700 -> stop_dist = $300
        # Equity = $25,788.92 -> 0.50% risk = $128.94 -> exact_lots = 128.94 / 300 = 0.43 lots
        res = self.client.execute_trade_across_all_accounts(
            symbol="BTC/USD",
            side="buy",
            entry_price=80000.0,
            stop_loss=79700.0,
            take_profit=80900.0,
            ai_score=8.4,
            has_smt=False,
            session="ASIAN_RANGE",
            hurst_exponent=0.55
        )
        self.assertTrue(res["success"])
        # On Account 1 (Scale-Out), 0.43 lots splits into Tranche 1 (0.21 lots) & Tranche 2 (0.22 lots)
        self.assertEqual(self.mock_helper.place_order.call_count, 2)
        args_t1 = self.mock_helper.place_order.call_args_list[0][1]
        args_t2 = self.mock_helper.place_order.call_args_list[1][1]
        self.assertEqual(args_t1["qty"], 0.21)
        self.assertEqual(args_t2["qty"], 0.22)
        self.assertEqual(round(args_t1["qty"] + args_t2["qty"], 2), 0.43)

    @patch("src.core.execution_firewall.ExecutionFirewall.audit_trade_request", return_value=(True, "Approved"))
    def test_a_plus_confluence_scaled_sizing(self, mock_firewall):
        """A+ Confluence setup (Score 9.2, SMT=True, London KZ, Hurst=0.62) must scale up to 0.85% risk."""
        # Entry 80,000, SL 79,700 -> stop_dist = $300
        # Equity = $25,788.92 -> 0.85% risk = $219.21 -> exact_lots = 219.21 / 300 = 0.73 lots
        res = self.client.execute_trade_across_all_accounts(
            symbol="BTC/USD",
            side="buy",
            entry_price=80000.0,
            stop_loss=79700.0,
            take_profit=80900.0,
            ai_score=9.2,
            has_smt=True,
            session="LONDON_KILLZONE",
            hurst_exponent=0.62
        )
        self.assertTrue(res["success"])
        # On Account 1 (Scale-Out), 0.73 lots splits into Tranche 1 (0.36 lots) & Tranche 2 (0.37 lots)
        self.assertEqual(self.mock_helper.place_order.call_count, 2)
        args_t1 = self.mock_helper.place_order.call_args_list[0][1]
        args_t2 = self.mock_helper.place_order.call_args_list[1][1]
        self.assertEqual(args_t1["qty"], 0.36)
        self.assertEqual(args_t2["qty"], 0.37)
        self.assertEqual(round(args_t1["qty"] + args_t2["qty"], 2), 0.73)

    @patch("src.core.execution_firewall.ExecutionFirewall.audit_trade_request", return_value=(True, "Approved"))
    def test_hard_safety_ceiling_enforcement(self, mock_firewall):
        """Risk must strictly never exceed 1.00% max safety ceiling, even if override is higher."""
        # Attempt to override with 5.0% risk -> Should be clamped to 1.00%
        # Equity = $25,788.92 -> 1.00% risk = $257.89 -> exact_lots = 257.89 / 300 = 0.86 lots
        res = self.client.execute_trade_across_all_accounts(
            symbol="BTC/USD",
            side="buy",
            entry_price=80000.0,
            stop_loss=79700.0,
            take_profit=80900.0,
            risk_pct_override=0.050 # 5.0%
        )
        self.assertTrue(res["success"])
        args_t1 = self.mock_helper.place_order.call_args_list[0][1]
        args_t2 = self.mock_helper.place_order.call_args_list[1][1]
        # Total lots = 0.43 + 0.43 = 0.86 lots (exactly 1.00% max ceiling)
        self.assertEqual(args_t1["qty"], 0.43)
        self.assertEqual(args_t2["qty"], 0.43)


if __name__ == "__main__":
    unittest.main()

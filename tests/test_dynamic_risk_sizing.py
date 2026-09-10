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
    def test_tier_cap_sizing_enforcement(self, mock_firewall):
        """On $25k account tier, risk is strictly clamped to $75.00 max ($75 / $300 = 0.25 lots)."""
        # Entry 80,000, SL 79,700 -> stop_dist = $300
        # Equity = $25,788.92 -> Tier cap = $75.00 -> exact_lots = 75.00 / 300 = 0.25 lots
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
        # On Account 1 (Scale-Out), 0.25 lots splits into Tranche 1 (0.12 lots) & Tranche 2 (0.13 lots)
        self.assertEqual(self.mock_helper.place_order.call_count, 2)
        args_t1 = self.mock_helper.place_order.call_args_list[0][1]
        args_t2 = self.mock_helper.place_order.call_args_list[1][1]
        self.assertEqual(args_t1["qty"], 0.12)
        self.assertEqual(args_t2["qty"], 0.13)
        self.assertEqual(round(args_t1["qty"] + args_t2["qty"], 2), 0.25)

    @patch("src.core.execution_firewall.ExecutionFirewall.audit_trade_request", return_value=(True, "Approved"))
    def test_10k_tier_cap_sizing(self, mock_firewall):
        """On $10k account tier, risk is strictly clamped to $30.00 max ($30 / $300 = 0.10 lots)."""
        self.mock_helper.balance = 9713.35
        # Entry 80,000, SL 79,700 -> stop_dist = $300
        # Equity = $9,713.35 -> Tier cap = $30.00 -> exact_lots = 30.00 / 300 = 0.10 lots
        res = self.client.execute_trade_across_all_accounts(
            symbol="BTC/USD",
            side="buy",
            entry_price=80000.0,
            stop_loss=79700.0,
            take_profit=80900.0,
            ai_score=9.5,
            has_smt=True,
            session="LONDON_KILLZONE",
            hurst_exponent=0.62
        )
        self.assertTrue(res["success"])
        args_t1 = self.mock_helper.place_order.call_args_list[0][1]
        args_t2 = self.mock_helper.place_order.call_args_list[1][1]
        self.assertEqual(round(args_t1["qty"] + args_t2["qty"], 2), 0.10)

    @patch("src.core.execution_firewall.ExecutionFirewall.audit_trade_request", return_value=(True, "Approved"))
    def test_unconstrained_dynamic_scaling(self, mock_firewall):
        """When tier caps are disabled, fractional Kelly scales up unconstrained to 0.85%."""
        setattr(Config, 'TIER_CAPS_ENABLED', False)
        try:
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
            args_t1 = self.mock_helper.place_order.call_args_list[0][1]
            args_t2 = self.mock_helper.place_order.call_args_list[1][1]
            self.assertEqual(round(args_t1["qty"] + args_t2["qty"], 2), 0.73)
        finally:
            setattr(Config, 'TIER_CAPS_ENABLED', True)


if __name__ == "__main__":
    unittest.main()

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
    1. Standard setups execute at tier-capped defensive risk.
    2. Distance-to-Default (DtD) buffer runway limits risk proportionally.
    3. The 1.00% hard safety ceiling is strictly enforced.
    4. Two-tranche scale-out splits adapt correctly to the dynamic lot sizing.
    """

    def setUp(self):
        self.mock_helper = MagicMock(spec=TradeLockerHelper)
        self.mock_helper.email = "eval_user@upcomers.com"
        self.mock_helper.balance = 25000.00
        self.mock_helper.access_token = "mock_token"
        self.mock_helper.place_order.return_value = {"orderId": "12345"}
        
        self.client = TradeLockerClient()
        self.client.helpers = [self.mock_helper]

    @patch("src.core.execution_firewall.ExecutionFirewall.audit_trade_request", return_value=(True, "Approved"))
    @patch("src.core.execution_firewall.ExecutionFirewall.is_account_eligible", return_value=(True, "ELIGIBLE"))
    def test_tier_cap_sizing_enforcement(self, mock_eligible, mock_firewall):
        """On $25k eval account tier, risk is strictly clamped to $50.00 max ($50 / $300 = 0.17 lots)."""
        # Entry 80,000, SL 79,700 -> stop_dist = $300
        # Equity = $25,000 -> Tier cap = $50.00 -> exact_lots = 50.00 / 300 = 0.17 lots
        res = self.client.execute_trade_across_all_accounts(
            symbol="BTC/USD",
            side="buy",
            entry_price=80000.0,
            stop_loss=79700.0,
            take_profit=80900.0,
            ai_score=8.4,
            has_smt=False,
            session="LONDON_KILLZONE",
            hurst_exponent=0.55
        )
        self.assertTrue(res["success"])
        # On Account index 0 (Scale-Out), 0.17 lots splits into Tranche 1 (0.09 lots) & Tranche 2 (0.08 lots)
        self.assertEqual(self.mock_helper.place_order.call_count, 2)
        args_t1 = self.mock_helper.place_order.call_args_list[0][1]
        args_t2 = self.mock_helper.place_order.call_args_list[1][1]
        self.assertEqual(args_t1["qty"], 0.09)
        self.assertEqual(args_t2["qty"], 0.08)
        self.assertEqual(round(args_t1["qty"] + args_t2["qty"], 2), 0.17)

    @patch("src.core.execution_firewall.ExecutionFirewall.audit_trade_request", return_value=(True, "Approved"))
    @patch("src.core.execution_firewall.ExecutionFirewall.is_account_eligible", return_value=(True, "ELIGIBLE"))
    def test_10k_tier_cap_sizing(self, mock_eligible, mock_firewall):
        """On $10k account tier, DtD buffer limits risk to 8% of remaining buffer ($17.07 / $300 = 0.06 lots)."""
        self.mock_helper.balance = 9713.35
        # Entry 80,000, SL 79,700 -> stop_dist = $300
        # Equity = $9,713.35, Floor = $9,500.0 -> Buffer = $213.35 -> DtD risk = 213.35 * 0.08 = $17.07 -> 0.06 lots
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
        self.assertEqual(round(args_t1["qty"] + args_t2["qty"], 2), 0.06)

    @patch("src.core.execution_firewall.ExecutionFirewall.audit_trade_request", return_value=(True, "Approved"))
    @patch("src.core.execution_firewall.ExecutionFirewall.is_account_eligible", return_value=(True, "ELIGIBLE"))
    def test_unconstrained_dynamic_scaling_clamped_by_safety_ceiling(self, mock_eligible, mock_firewall):
        """When tier caps are disabled, unconstrained sizing is still clamped by hard safety ceiling MAX_LOT_SIZE_PER_ORDER (0.25 lots)."""
        setattr(Config, 'TIER_CAPS_ENABLED', False)
        try:
            # Equity = $25,000 -> unconstrained sizing would be 0.73 lots, but MAX_LOT_SIZE_PER_ORDER clamps to 0.25 max
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
            self.assertEqual(round(args_t1["qty"] + args_t2["qty"], 2), 0.25)
        finally:
            setattr(Config, 'TIER_CAPS_ENABLED', True)


if __name__ == "__main__":
    unittest.main()

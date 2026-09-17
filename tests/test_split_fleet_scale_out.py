import unittest
from unittest.mock import MagicMock, patch, mock_open
from src.core.config import Config
from src.clients.tl_client import TradeLockerClient, TradeLockerHelper

class TestSplitFleetScaleOut(unittest.TestCase):
    def setUp(self):
        patcher = patch("src.clients.telegram_notifier.TelegramNotifier._send_message")
        self.mock_tg = patcher.start()
        self.addCleanup(patch.stopall)

    def test_split_fleet_configuration_parameters(self):
        """Verify Split-Fleet Barbell architecture config settings."""
        self.assertTrue(Config.SPLIT_FLEET_SCALE_OUT_ENABLED)
        self.assertIn(0, Config.SCALE_OUT_ACCOUNT_INDICES) # Account 1 (Payout Account)
        self.assertIn(2, Config.SCALE_OUT_ACCOUNT_INDICES)
        self.assertIn(3, Config.SCALE_OUT_ACCOUNT_INDICES)
        self.assertIn(4, Config.SCALE_OUT_ACCOUNT_INDICES)
        
        self.assertIn(1, Config.FULL_RUNNER_ACCOUNT_INDICES)
        self.assertIn(5, Config.FULL_RUNNER_ACCOUNT_INDICES)
        self.assertIn(6, Config.FULL_RUNNER_ACCOUNT_INDICES)
        self.assertIn(7, Config.FULL_RUNNER_ACCOUNT_INDICES)
        
        self.assertEqual(Config.SCALE_OUT_TP1_R, 2.0)
        self.assertEqual(Config.SCALE_OUT_TP1_PCT, 0.50)

    @patch("builtins.open", mock_open(read_data='{"date": "2099-01-01", "setups_fired": 0}'))
    @patch.object(TradeLockerHelper, 'place_order')
    @patch.object(TradeLockerHelper, 'login')
    def test_two_tranche_dispatch_on_scale_out_accounts(self, mock_login, mock_place_order):
        """Verify scale-out accounts place two tranches (TP1 @ 2.0R, TP2 @ full TP) and runner accounts place 1 order."""
        mock_login.return_value = True
        mock_place_order.return_value = {"orderId": "ord_123"}

        tl = TradeLockerClient()
        # Mock 2 helpers: Helper 0 (Scale-Out) and Helper 1 (Full Runner)
        helper0 = TradeLockerHelper("acc1@upcomers.com", "p", "s", "http://api")
        helper0.access_token = "token"
        helper0.balance = 25000.0
        helper0.place_order = MagicMock(return_value={"orderId": "t1"})
        helper0.get_open_positions = MagicMock(return_value=[])

        helper1 = TradeLockerHelper("acc2@upcomers.com", "p", "s", "http://api")
        helper1.access_token = "token"
        helper1.balance = 50000.0
        helper1.place_order = MagicMock(return_value={"orderId": "runner"})
        helper1.get_open_positions = MagicMock(return_value=[])

        tl.helpers = [helper0, helper1]

        with patch("time.sleep"):
            res = tl.execute_trade_across_all_accounts(
                symbol="BTC/USD",
                side="sell",
                entry_price=77800.0,
                stop_loss=78000.0,   # stop dist = 200 pts
                take_profit=77200.0,  # 600 pt target (3.0R)
                risk_scale=1.00,
                bypass_firewall=True
            )

        self.assertTrue(res["success"])
        # Helper 0 (Scale-Out) should have called place_order TWICE (Tranche 1 @ 2.0R and Tranche 2 @ 3.0R)
        self.assertEqual(helper0.place_order.call_count, 2)
        call1 = helper0.place_order.call_args_list[0][1]
        call2 = helper0.place_order.call_args_list[1][1]
        
        # Sizing on 25k @ 0.5% ($125 risk) / 200 pts = 0.62 lots
        # Tranche 1: 0.31 lots, TP1 = 77800 - (2.0 * 200) = 77400.0 (+15.0 cushion = 77415.0)
        cushion = getattr(Config, 'TP_FRONT_RUN_CUSHION_USD', {}).get('BTC', 0.0) if getattr(Config, 'TP_FRONT_RUN_CUSHION_ENABLED', False) else 0.0
        self.assertEqual(call1["take_profit"], 77400.0 + cushion)
        # Tranche 2: 0.31 lots, TP2 = 77200.0 (Full TP)
        self.assertEqual(call2["take_profit"], 77200.0)

        # Helper 1 (Full Runner) should have called place_order ONCE with full TP
        self.assertEqual(helper1.place_order.call_count, 1)
        runner_call = helper1.place_order.call_args[1]
        self.assertEqual(runner_call["take_profit"], 77200.0)

if __name__ == '__main__':
    unittest.main()

import unittest
from unittest.mock import MagicMock, patch
from scripts.position_watchdog import PositionWatchdog
from src.clients.tl_client import TradeLockerHelper, TradeLockerClient

class TestWatchdogAndScaleoutInvariants(unittest.TestCase):

    def test_watchdog_broker_native_stop_loss_resolution(self):
        """Verify watchdog retrieves stop loss directly from position object without DB dependencies."""
        watchdog = PositionWatchdog()
        
        pos_with_sl = {
            "id": "pos_123",
            "symbol": "BTCUSD",
            "price": 76682.0,
            "stopLoss": 76859.15,
            "takeProfit": 75939.59,
            "pnl": 211.0,
            "qty": 0.42
        }
        
        sl, scan = watchdog.get_stop_loss("BTCUSD", pos=pos_with_sl)
        self.assertEqual(sl, 76859.15)
        self.assertIsNone(scan)

    def test_watchdog_r_multiple_calculation(self):
        """Verify R-multiple calculation when trade moves into profit."""
        watchdog = PositionWatchdog()
        pos = {
            "id": "pos_123",
            "symbol": "BTCUSD",
            "price": 76682.0,
            "stopLoss": 76859.0, # risk = 177 pts
            "pnl": 211.0,
            "qty": 0.42
        }
        
        sl, _ = watchdog.get_stop_loss(pos["symbol"], pos=pos)
        entry = pos["price"]
        qty = pos["qty"]
        risk_usd = abs(entry - sl) * qty * 1.0 # BTC contract size = 1.0
        
        # 177 pts * 0.42 = $74.34 risk
        # $211.0 / $74.34 = 2.838R
        r_multiple = pos["pnl"] / risk_usd
        self.assertAlmostEqual(r_multiple, 2.838, places=2)
        self.assertGreaterEqual(r_multiple, 1.5)

    @patch.object(TradeLockerHelper, 'modify_position_bracket')
    @patch.object(TradeLockerHelper, 'get_open_positions')
    @patch.object(TradeLockerHelper, 'login')
    def test_two_tranche_split_bracket_preservation(self, mock_login, mock_get_pos, mock_modify):
        """Verify Tranche 1 is NOT overwritten when Tranche 2 is placed."""
        mock_login.return_value = True
        helper = TradeLockerHelper("test@upcomers.com", "pass", "srv", "http://fake")
        helper.account_id = "123"
        helper.access_token = "token"

        # Position 1 created by Tranche 1
        pos1 = {
            "id": "pos_T1",
            "instrumentId": "19965",
            "symbol": "BTCUSD",
            "side": "SELL",
            "qty": 0.20,
            "price": 76682.0,
            "stopLoss": 76859.0,
            "takeProfit": 76169.0
        }
        # Position 2 created by Tranche 2
        pos2 = {
            "id": "pos_T2",
            "instrumentId": "19965",
            "symbol": "BTCUSD",
            "side": "SELL",
            "qty": 0.22,
            "price": 76682.0,
            "stopLoss": 76859.0,
            "takeProfit": 75939.0
        }

        # First call to place_order: returns pos1 in open_positions
        mock_get_pos.side_effect = [
            [], # pre_pos before T1
            [pos1], # post_pos after T1
            [pos1], # pre_pos before T2 (pos1 already exists!)
            [pos1, pos2] # post_pos after T2 (both exist now)
        ]
        mock_modify.return_value = True

        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"orderId": "ord_1"}

            # Place Tranche 1
            res1 = helper.place_order(
                instrument_id="19965",
                side="sell",
                qty=0.20,
                stop_loss=76859.0,
                take_profit=76169.0
            )

            # Place Tranche 2
            res2 = helper.place_order(
                instrument_id="19965",
                side="sell",
                qty=0.22,
                stop_loss=76859.0,
                take_profit=75939.0
            )

        # modify_position_bracket should have been called TWICE: once for pos_T1, once for pos_T2
        self.assertEqual(mock_modify.call_count, 2)
        call_1_pos_id = mock_modify.call_args_list[0][0][0]
        call_1_tp = mock_modify.call_args_list[0][1]["take_profit"]
        
        call_2_pos_id = mock_modify.call_args_list[1][0][0]
        call_2_tp = mock_modify.call_args_list[1][1]["take_profit"]

        self.assertEqual(call_1_pos_id, "pos_T1")
        self.assertEqual(call_1_tp, 76169.0)

        self.assertEqual(call_2_pos_id, "pos_T2")
        self.assertEqual(call_2_tp, 75939.0)

if __name__ == "__main__":
    unittest.main()

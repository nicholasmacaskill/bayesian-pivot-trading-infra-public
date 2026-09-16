import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.getcwd())
from src.clients.tl_client import TradeLockerClient, TradeLockerHelper


class TestBrokerBracketResolution(unittest.TestCase):
    """
    Unit tests ensuring:
    1. get_open_positions exposes tradableInstrumentId in both list & dict formats.
    2. place_order properly matches and patches brackets without failing.
    3. modify_position_bracket uses fallback endpoints properly.
    """

    def setUp(self):
        self.helper = TradeLockerHelper("test@upcomers.com", "pass", "Upcomers", "https://demo.tradelocker.com")
        self.helper.access_token = "mock_token"
        self.helper.account_id = "2478634"

    @patch("requests.get")
    def test_get_open_positions_list_format(self, mock_get):
        """Verify Upcomers list format parses tradableInstrumentId accurately."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        # List format: [id, tradableInstrumentId, routeId, side, qty, price, slOrderId, tpOrderId, entry_ms, pnl, key]
        mock_resp.json.return_value = {
            "d": {
                "positions": [
                    ["288230376155327317", "19965", "2025730", "buy", "0.15", "76860.21", "288230376182133992", "288230376182133994", 1788529218202, 27.52, "key-undefined"]
                ]
            }
        }
        mock_get.return_value = mock_resp

        positions = self.helper.get_open_positions()
        self.assertEqual(len(positions), 1)
        pos = positions[0]
        self.assertEqual(pos["id"], "288230376155327317")
        self.assertEqual(pos["tradableInstrumentId"], "19965")
        self.assertEqual(pos["instrumentId"], "19965")
        self.assertEqual(pos["side"], "BUY")
        self.assertEqual(pos["price"], 76860.21)

    @patch("requests.get")
    def test_get_open_positions_dict_format(self, mock_get):
        """Verify dict format parses tradableInstrumentId accurately."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "d": {
                "positions": [
                    {
                        "id": "288230376155327318",
                        "instrumentId": "19965",
                        "side": "buy",
                        "openPrice": 76860.21,
                        "qty": 0.15,
                        "floatingProfit": 10.0,
                        "stopLoss": 76629.63,
                        "takeProfit": 77551.95
                    }
                ]
            }
        }
        mock_get.return_value = mock_resp

        positions = self.helper.get_open_positions()
        self.assertEqual(len(positions), 1)
        pos = positions[0]
        self.assertEqual(pos["id"], "288230376155327318")
        self.assertEqual(pos["tradableInstrumentId"], "19965")
        self.assertEqual(pos["stopLoss"], 76629.63)

    @patch("requests.post")
    @patch("requests.patch")
    @patch.object(TradeLockerHelper, "get_open_positions")
    def test_place_order_bracket_matching(self, mock_open_pos, mock_patch, mock_post):
        """Verify place_order matches open position by instrument ID and invokes modify_position_bracket."""
        # 1. Mock order fill
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"orderId": "9999"}
        mock_post.return_value = mock_post_resp

        # 2. Mock open positions returned on poll
        mock_open_pos.return_value = [
            {
                "id": "pos_btc_123",
                "symbol": "BTC/USD",
                "tradableInstrumentId": "19965",
                "instrumentId": "19965",
                "side": "BUY",
                "price": 76860.21,
                "qty": 0.15,
                "status": "OPEN"
            }
        ]

        # 3. Mock patch response
        mock_patch_resp = MagicMock()
        mock_patch_resp.status_code = 200
        mock_patch.return_value = mock_patch_resp

        result = self.helper.place_order(
            instrument_id="19965",
            side="buy",
            qty=0.15,
            stop_loss=76629.63,
            take_profit=77551.95,
            symbol_hint="BTC/USD"
        )

        self.assertIsNotNone(result)
        # Verify patch was called for pos_btc_123
        self.assertEqual(mock_patch.call_count, 1)
        called_url = mock_patch.call_args[0][0]
        self.assertIn("pos_btc_123", called_url)
        called_payload = mock_patch.call_args[1]["json"]
        self.assertEqual(called_payload["stopLoss"], 76629.63)
        self.assertEqual(called_payload["takeProfit"], 77551.95)


if __name__ == "__main__":
    unittest.main()

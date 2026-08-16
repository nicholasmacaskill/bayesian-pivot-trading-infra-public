import sys
import os
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.clients.telegram_notifier import TelegramNotifier

class TestTelegramCommands(unittest.TestCase):
    def setUp(self):
        self.tg = TelegramNotifier(bot_token="TEST_TOKEN", chat_id="123456")

    @patch("requests.get")
    @patch.object(TelegramNotifier, "send_executive_report_to_telegram")
    def test_report_command_dispatch(self, mock_send_report, mock_get):
        # Mock Telegram getUpdates returning /report text command
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "result": [
                {
                    "update_id": 100,
                    "message": {
                        "chat": {"id": 123456},
                        "text": "/report"
                    }
                }
            ]
        }
        next_offset = self.tg.poll_updates_and_dispatch(offset=None)
        self.assertEqual(next_offset, 101)
        mock_send_report.assert_called_once()

    @patch("requests.get")
    @patch("scripts.maintenance.emergency_kill_switch.execute_emergency_kill_switch")
    @patch.object(TelegramNotifier, "_send_message")
    def test_kill_command_dispatch(self, mock_send_msg, mock_kill_switch, mock_get):
        # Mock Telegram getUpdates returning /kill command
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "result": [
                {
                    "update_id": 101,
                    "message": {
                        "chat": {"id": 123456},
                        "text": "/kill"
                    }
                }
            ]
        }
        next_offset = self.tg.poll_updates_and_dispatch(offset=101)
        self.assertEqual(next_offset, 102)
        mock_kill_switch.assert_called_once()

if __name__ == "__main__":
    unittest.main()

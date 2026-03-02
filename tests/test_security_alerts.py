import sys
import os
from unittest.mock import MagicMock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.clients.telegram_notifier import TelegramNotifier

def test_security_alert_format():
    print("🧪 Testing Security Alert Formatting...")
    
    # Mock bot and chat_id
    notifier = TelegramNotifier(bot_token="MOCK_TOKEN", chat_id="MOCK_ID")
    notifier._send_message = MagicMock()
    
    # Test Clean Status
    print("Checking CLEAN status...")
    notifier.send_alert(
        symbol="BTC/USDT",
        timeframe="4h",
        pattern="Bullish FVG",
        ai_score=8.7,
        reasoning="Strong displacement",
        security_status="System security: CLEAN (trust score: 100/100)"
    )
    
    args, kwargs = notifier._send_message.call_args
    message = args[0]
    print(f"Message preview:\n{message[:200]}...")
    assert "Environment confirmed as secure" in message
    assert "BTC/USDT" in message
    
    # Test Threat Status
    print("Checking THREAT status...")
    notifier.send_alert(
        symbol="ETH/USDT",
        timeframe="1h",
        pattern="Bearish OB",
        ai_score=7.2,
        reasoning="Liquidity sweep",
        security_status="⚠️ System security: THREAT DETECTED — CLIPBOARD_THREAT"
    )
    
    args, kwargs = notifier._send_message.call_args
    message = args[0]
    print(f"Message preview:\n{message[:200]}...")
    assert "⚠️ *Security:*" in message
    assert "CLIPBOARD_THREAT" in message

    print("✅ All format tests passed!")

if __name__ == "__main__":
    try:
        test_security_alert_format()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)

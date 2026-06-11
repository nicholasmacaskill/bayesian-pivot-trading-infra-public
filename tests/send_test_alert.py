import sys
import os
import time
from datetime import datetime

# Add root directory to path
sys.path.append(os.getcwd())

# Auto-load .env.local if present
if os.path.exists(".env.local"):
    with open(".env.local", "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

from src.clients.telegram_notifier import TelegramNotifier
from src.core.config import Config

class MockRegimeResult:
    def __init__(self):
        self.suggested_size_mult = 1.0
        self.atr_percentile = 65
        
        class MockRegime:
            value = "TREND"
        self.regime = MockRegime()

def send_test_alert():
    print("📤 Dispatching test Telegram alert for Sovereign Light setup...")
    
    # Load credentials
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        print("❌ Error: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables must be set.")
        sys.exit(1)
        
    notifier = TelegramNotifier(bot_token=bot_token, chat_id=chat_id)
    
    # Unique pattern name to bypass the 60-minute duplicate suppression filter
    unique_pattern = f"Bullish FVG Retest (Test {int(time.time())})"
    
    # Mocking risk calculations for a 2.5 R:R setup aiming for $350 profit
    # Target R:R = 2.5. Risk = $140. Profit target = $350.
    risk_calc = {
        "entry": 67420.0,
        "stop_loss": 67220.0, # $200 stop distance
        "take_profit": 67920.0, # $500 target distance
        "risk_reward": 2.5,
        "position_size": 0.7000, # 0.7 lots * $200 = $140 risk
        "position_value": 47194.0 # 0.7 * 67420
    }
    
    health = {
        "daily_drawdown": 0.004, # 0.4%
        "equity_buffer_usd": 6120.0, # buffer to daily limit
    }
    
    session = {
        "name": "NY_CONTINUOUS",
        "phase": "AM_SESSION"
    }
    
    bias = {
        "daily": "BULLISH",
        "htf": "BULLISH",
        "dxy_trend": "BEARISH_SWEEP"
    }
    
    liquidity = {
        "target_price": 68150.0,
        "target_type": "EQH",
        "distance_pips": 73.0
    }
    
    notifier.send_alert(
        symbol="BTC/USD",
        timeframe="5m",
        pattern=unique_pattern,
        ai_score=10.0, # Default perfect score for Sovereign Light bypass mode
        reasoning="Sovereign Light Mode Active (AI Gate Bypassed). Entry triggers on LTF 5m bullish FVG tap following DXY liquidity sweep.",
        verdict="ACCEPTED",
        risk_calc=risk_calc,
        regime_result=MockRegimeResult(),
        health_report=health,
        bias_data=bias,
        liquidity_targets=liquidity,
        session_info=session,
        shadow_insights={"slippage_estimate": "0.02% (Optimal)"},
        psych_data={"mood": "Focused (Biometric Bypass)"}
    )
    
    print("✅ Test alert successfully sent to Telegram!")

if __name__ == "__main__":
    send_test_alert()

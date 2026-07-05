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

class MockRegimeResult:
    def __init__(self):
        self.suggested_size_mult = 1.0
        self.atr_percentile = 42
        
        class MockRegime:
            value = "RANGE"
        self.regime = MockRegime()

def send_test_alpha_sweep_alert():
    print("📤 Dispatching test Sovereign Turtle Soup alert...")
    
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        print("❌ Error: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set.")
        sys.exit(1)
        
    notifier = TelegramNotifier(bot_token=bot_token, chat_id=chat_id)
    
    unique_pattern = f"Bayesian Pivot Turtle Soup LONG (MEAN_REVERSION) [Test]"
    
    risk_calc = {
        "entry": 64500.0,
        "stop_loss": 64250.0,
        "take_profit": 66375.0,
        "risk_reward": 7.5,
        "position_size": 0.4000,
        "position_value": 25800.0
    }
    
    health = {
        "daily_drawdown": 0.0,
        "equity_buffer_usd": 7500.0,
    }
    
    session = {
        "name": "LONDON_OPEN",
        "phase": "EXECUTION"
    }
    
    bias = {
        "daily": "SIDEWAYS",
        "htf": "RANGE-BOUND",
        "dxy_trend": "N/A"
    }
    
    liquidity = {
        "target_price": 64620.0,
        "target_type": "SWING_LOW",
        "distance_pips": 120.0
    }
    
    notifier.send_alert(
        symbol="BTC/USD",
        timeframe="5m",
        pattern=unique_pattern,
        ai_score=9.0,
        reasoning="Turtle Soup Liquidity Sweep of HTF level 64620.00. Hurst: 0.380 (MEAN_REVERSION). Wick Rejection confirmed on 5m candle.",
        verdict="ACCEPTED",
        risk_calc=risk_calc,
        regime_result=MockRegimeResult(),
        health_report=health,
        bias_data=bias,
        liquidity_targets=liquidity,
        session_info=session,
        shadow_insights={"slippage_estimate": "0.01% (Optimal)"},
        psych_data={"mood": "Focused (Biometric Secure)"}
    )
    
    print("✅ Bayesian Pivot test alert successfully sent!")

if __name__ == "__main__":
    send_test_alpha_sweep_alert()

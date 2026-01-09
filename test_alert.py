#!/usr/bin/env python3
"""
Test script to send a sample Telegram alert
"""
from telegram_notifier import TelegramNotifier
from dotenv import load_dotenv

# Load environment variables
load_dotenv(".env.local")

def test_alert():
    """Send a test alert to verify Telegram integration"""
    notifier = TelegramNotifier()
    
    # Sample setup data
    test_setup = {
        "symbol": "BTC/USDT",
        "pattern": "Bullish PO3 (Judas Swing)",
        "bias": "BULLISH",
        "entry": 42850.50,
        "stop_loss": 42500.00,
        "target": 43550.00
    }
    
    # Sample AI validation
    ai_result = {
        "score": 8.7,
        "reasoning": "The draw on liquidity is obvious. This Judas swing cleared the Asian lows efficiently, sweeping weak hands before institutional accumulation. HTF bias confirms bullish structure.",
        "guidance": "Execute at the 62% retrace of the displacement candle. Target the daily FVG at $43,550."
    }
    
    # Sample risk calculation
    risk_calc = {
        "entry": test_setup["entry"],
        "stop_loss": test_setup["stop_loss"],
        "position_size": 0.023,
        "equity_basis": 100000.0,
        "is_ip_safe": True,
        "sentiment": "Greed (72)"
    }
    
    print("📨 Sending test alert to Telegram...")
    notifier.send_alert(
        symbol=test_setup["symbol"],
        timeframe="15m",
        pattern=test_setup["pattern"],
        ai_score=ai_result["score"],
        reasoning=ai_result["reasoning"],
        risk_calc=risk_calc
    )
    print("✅ Test alert sent! Check your Telegram (@SovSMCbot)")

if __name__ == "__main__":
    test_alert()

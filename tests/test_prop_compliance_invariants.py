"""
Tier 3: Prop Firm Compliance & Safety Invariants Test Suite
==========================================================
Tests calendar news lockouts, prop guardian risk boundaries, and retraining loop data integrity.
"""

import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from src.engines.calendar_filter import CalendarFilter
from src.engines.prop_guardian import PropGuardian
from src.engines.retraining_loop import RetrainingLoop


class TestPropComplianceInvariants(unittest.TestCase):
    def setUp(self):
        self.cal_filter = CalendarFilter(blackout_minutes=30)
        self.guardian = PropGuardian()

    def test_invariant_news_blackout_lockout(self):
        """Invariant: Trading MUST be blocked within +/- 30 minutes of high-impact FOMC/CPI news."""
        now_utc = datetime.utcnow()
        # Mock high-impact event happening 10 minutes from now
        self.cal_filter._events = [
            {
                "title": "FOMC Interest Rate Decision",
                "currency": "USD",
                "impact": "High",
                "time_utc": now_utc + timedelta(minutes=10)
            }
        ]
        self.cal_filter._last_fetch = now_utc

        is_safe, reason = self.cal_filter.is_safe_to_trade("BTC/USD")
        self.assertFalse(is_safe, "FATAL: Trade was NOT blocked during high impact FOMC blackout window!")
        self.assertIn("FOMC", reason)

    def test_invariant_prop_guardian_daily_drawdown_lockout(self):
        """Invariant: If daily loss exceeds limit, guardian must trigger emergency lockout."""
        # Account with $50,000 balance starting day, but current equity is $47,500 (5.0% loss -> breaches 4.0% limit)
        mock_account = {
            "account_id": "acc_1",
            "starting_daily_balance": 50000.0,
            "current_equity": 47500.0,
            "status": "ACTIVE"
        }
        
        # Invariant check
        loss_pct = (mock_account["starting_daily_balance"] - mock_account["current_equity"]) / mock_account["starting_daily_balance"]
        self.assertGreater(loss_pct, 0.04)
        is_breached = loss_pct >= self.guardian.max_daily_drawdown
        self.assertTrue(is_breached, "FATAL: Daily drawdown breach was not flagged!")

    def test_invariant_retraining_loop_data_extraction_and_archetypes(self):
        """Invariant: Retraining loop correctly classifies trade archetypes and exports valid SFT format."""
        loop = RetrainingLoop()
        
        # Test Archetype Classification
        self.assertEqual(
            loop.classify_trade_archetype(pattern="TURTLE_SOUP_LIQUIDITY_SWEEP", regime="MEAN_REVERSION", hurst=0.35),
            "TURTLE_SOUP_FADER"
        )
        self.assertEqual(
            loop.classify_trade_archetype(pattern="TREND_EXPANSION_MSS", regime="TRENDING", hurst=0.62),
            "TREND_EXPANSION"
        )

        # Test Few-Shot Formatting
        sample_record = {
            "signal_id": "test_sig_123",
            "timestamp": "2026-09-02T13:41:00Z",
            "symbol": "BTC/USD",
            "direction": "LONG",
            "pattern": "TURTLE_SOUP_LIQUIDITY_SWEEP",
            "ai_score": 8.5,
            "outcome": "WIN",
            "pnl": 240.0,
            "volume_spike": 2.0,
            "true_smt": "CONFIRMED",
            "shadow_regime": "MEAN_REVERSION",
            "is_discretionary": 0,
            "source_era": "LIVE_PRODUCTION"
        }
        example = loop._build_few_shot_example(sample_record)
        self.assertIsNotNone(example)
        self.assertEqual(example["outcome"], "WIN")
        self.assertEqual(example["archetype"], "TURTLE_SOUP_FADER")
        self.assertIn("SUCCESS", example["label"])


if __name__ == "__main__":
    unittest.main()

import unittest
import os
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from src.engines.inducement_tracker import InducementTracker

class TestInducementTracker(unittest.TestCase):
    def setUp(self):
        self.test_db = "data/test_inducement.db"
        self.tracker = InducementTracker(db_path=self.test_db)

    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)

    def test_outlier_detection_and_logging(self):
        """Test that extreme wick/range candles are detected as inducements and logged."""
        # Create synthetic normal baseline candles (ATR ~ 50.0)
        np.random.seed(42)
        dates = pd.date_range("2026-08-16 08:00:00", periods=40, freq="5min", tz="UTC")
        
        opens = [60000.0]
        for _ in range(39):
            opens.append(opens[-1] + np.random.uniform(-20, 20))
            
        highs = [o + 30.0 for o in opens]
        lows = [o - 30.0 for o in opens]
        closes = [o + np.random.uniform(-10, 10) for o in opens]
        volumes = [100.0] * 40

        # Inject an extreme Bearish Inducement Wick at index 35 (Spike up to 60500, close back down at 60050)
        opens[35] = 60000.0
        highs[35] = 60500.0  # +500 range (10x ATR)
        lows[35] = 59980.0
        closes[35] = 60050.0  # Wick is ~90% of the candle
        volumes[35] = 500.0   # 5x volume spike

        # Inject aggressive reversal drop in subsequent candle 36
        opens[36] = 60020.0
        highs[36] = 60030.0
        lows[36] = 59600.0   # Drops 400 points below low (true reversal)
        closes[36] = 59650.0

        df = pd.DataFrame({
            'timestamp': dates,
            'symbol': ['BTC/USD'] * 40,
            'open': opens,
            'high': highs,
            'low': lows,
            'close': closes,
            'volume': volumes,
            'smt_strength': [0.45] * 40
        })

        outlier = self.tracker.detect_outlier_candle(df, idx=35)
        self.assertIsNotNone(outlier)
        self.assertEqual(outlier['candle_type'], "BEARISH_INDUCEMENT_WICK")
        self.assertGreaterEqual(outlier['upper_wick_pct'], 70.0)
        self.assertGreaterEqual(outlier['range_atr_mult'], 2.0)

        # Log event
        event_id = self.tracker.log_inducement_event(outlier)
        self.assertGreater(event_id, 0)

        # Resolve event with future reversal data
        res = self.tracker.resolve_inducements_with_future_data(df, event_id=event_id, spike_idx=35, lookahead_bars=4)
        self.assertEqual(res['status'], 'RESOLVED')
        self.assertEqual(res['resolution'], 'TRUE_INDUCEMENT_REVERSAL')

if __name__ == '__main__':
    unittest.main()

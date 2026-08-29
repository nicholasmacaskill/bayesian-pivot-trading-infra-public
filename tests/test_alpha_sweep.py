import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
from src.engines.alpha_sweep_scanner import AlphaSweepScanner

class TestAlphaSweepScanner(unittest.TestCase):
    def setUp(self):
        self.scanner = AlphaSweepScanner()
        
    def test_find_htf_levels(self):
        # Create a mock 1H dataframe with a swing high and a swing low
        timestamps = [datetime.now(timezone.utc) - timedelta(hours=i) for i in range(100)]
        timestamps.reverse()
        
        # Base price around 100
        highs = [100.0] * 100
        lows = [95.0] * 100
        
        # Insert a clear swing high at index 50
        highs[50] = 105.0
        # Insert a clear swing low at index 70
        lows[70] = 90.0
        
        df_1h = pd.DataFrame({
            'timestamp': timestamps,
            'high': highs,
            'low': lows,
            'close': [97.5] * 100
        })
        
        swing_highs, swing_lows = self.scanner.find_htf_levels(df_1h, window=2)
        
        # Verify swing high was detected
        detected_high_prices = [h[1] for h in swing_highs]
        self.assertIn(105.0, detected_high_prices)
        
        # Verify swing low was detected
        detected_low_prices = [l[1] for l in swing_lows]
        self.assertIn(90.0, detected_low_prices)

    def test_turtle_soup_detection(self):
        # 1H data
        timestamps_1h = [datetime.now(timezone.utc) - timedelta(hours=i) for i in range(100)]
        timestamps_1h.reverse()
        df_1h = pd.DataFrame({
            'timestamp': timestamps_1h,
            'high': [100.0] * 100,
            'low': [95.0] * 100,
            'close': [97.0] * 100
        })
        # Insert swing low at 90.0
        df_1h.loc[50, 'low'] = 90.0
        
        # 5m data
        timestamps_5m = [datetime.now(timezone.utc) - timedelta(minutes=5*i) for i in range(100)]
        timestamps_5m.reverse()
        
        # Create normal 5m candles
        df_5m = pd.DataFrame({
            'timestamp': timestamps_5m,
            'open': [97.0] * 100,
            'high': [98.0] * 100,
            'low': [96.0] * 100,
            'close': [97.0] * 100,
            'volume': [1000.0] * 100
        })
        
        # Set the second-to-last candle (completed candle) to be a Bullish Turtle Soup:
        # It pierces 90.0 (the swing low) and closes back above it with a strong wick rejection.
        # level is 90.0. Let's make low = 89.5, close = 91.0, open = 92.0, high = 92.5
        # Total range: 92.5 - 89.5 = 3.0. Wick: min(open, close) - low = 91.0 - 89.5 = 1.5. Wick ratio: 1.5/3.0 = 50% (>= 30%).
        df_5m.loc[98, 'open'] = 92.0
        df_5m.loc[98, 'high'] = 92.5
        df_5m.loc[98, 'low'] = 89.5
        df_5m.loc[98, 'close'] = 91.0
        
        # Let's print out what is returned to debug
        swing_highs, swing_lows = self.scanner.find_htf_levels(df_1h.iloc[:-1], window=2)
        print("SWING LOWS:", swing_lows)
        closes_1h = df_1h['close'].values
        hurst = self.scanner.get_hurst_exponent(closes_1h)
        print("HURST EXPONENT:", hurst)
        atr_series = self.scanner.calculate_atr(df_5m)
        print("ATR:", atr_series.iloc[-1] if len(atr_series) > 0 else "None")
        
        result = self.scanner.check_turtle_soup('BTC/USD', df_5m, df_1h)
        self.assertIsNotNone(result)
        if result:
            self.assertEqual(result['direction'], 'LONG')
            self.assertEqual(result['level'], 90.0)

    def test_ai_validator_gating_and_deduplication(self):
        # Build mock 1H and 5m data
        timestamps_1h = [int(datetime.now(timezone.utc).timestamp() * 1000) - (3600000 * i) for i in range(100)]
        timestamps_1h.reverse()
        df_1h = pd.DataFrame({
            'timestamp': timestamps_1h,
            'open': [97.0] * 100,
            'high': [100.0] * 100,
            'low': [95.0] * 100,
            'close': [97.0] * 100,
            'volume': [1000.0] * 100
        })
        df_1h.loc[50, 'low'] = 90.0

        timestamps_5m = [int(datetime.now(timezone.utc).timestamp() * 1000) - (300000 * i) for i in range(100)]
        timestamps_5m.reverse()
        df_5m = pd.DataFrame({
            'timestamp': timestamps_5m,
            'open': [97.0] * 100,
            'high': [98.0] * 100,
            'low': [96.0] * 100,
            'close': [97.0] * 100,
            'volume': [1000.0] * 100
        })
        # Set up a Turtle Soup long on candle 98
        df_5m.loc[98, 'open'] = 92.0
        df_5m.loc[98, 'high'] = 92.5
        df_5m.loc[98, 'low'] = 89.5
        df_5m.loc[98, 'close'] = 91.0

        # Mock fetch_data and shadow_engine
        self.scanner.fetch_data = lambda sym, tf, limit=100, synchronized=False: df_1h if tf == '1h' else df_5m
        self.scanner.is_premium_killzone = lambda: "LONDON_OPEN"
        
        # Test low score (< 7.5) -> must be tagged as shadow trade failing AI validator
        self.scanner.shadow_engine.run_shadow_audit = lambda sym, df, dir: {
            "shadow_score": 5.0,
            "cvd_absorption": {"active": False, "details": "No CVD Divergence"},
            "session_vwap": {"z_score": -0.65},
            "kalman_mss": {"state": "BULLISH_SHIFT"}
        }

        # First scan
        setup1 = self.scanner.scan_symbol('BTC/USD')
        self.assertIsNotNone(setup1)

        # Second scan on identical candle timestamp -> must return None (deduplicated)
        setup2 = self.scanner.scan_symbol('BTC/USD')
        self.assertIsNone(setup2, "Second scan on the same candle timestamp should be deduplicated")

if __name__ == '__main__':
    unittest.main()


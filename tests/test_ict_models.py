import unittest
import pandas as pd
import numpy as np
from src.engines.smc_scanner import SMCScanner

class TestICTModels(unittest.TestCase):
    def setUp(self):
        self.scanner = SMCScanner()

    def test_optimal_trade_entry_long(self):
        # Swing Low = 60,000, Swing High = 70,000 (Range = 10,000)
        ote = self.scanner.calculate_ote(swing_low=60000.0, swing_high=70000.0, direction="LONG")
        self.assertEqual(ote["direction"], "LONG")
        self.assertEqual(ote["ote_62"], 63800.0)      # 70000 - 6200
        self.assertEqual(ote["ote_sweet_spot"], 62950.0) # 70000 - 7050
        self.assertEqual(ote["ote_79"], 62100.0)      # 70000 - 7900

    def test_optimal_trade_entry_short(self):
        # Swing Low = 60,000, Swing High = 70,000 (Range = 10,000)
        ote = self.scanner.calculate_ote(swing_low=60000.0, swing_high=70000.0, direction="SHORT")
        self.assertEqual(ote["direction"], "SHORT")
        self.assertEqual(ote["ote_62"], 66200.0)      # 60000 + 6200
        self.assertEqual(ote["ote_sweet_spot"], 67050.0) # 60000 + 7050
        self.assertEqual(ote["ote_79"], 67900.0)      # 60000 + 7900

    def test_fvg_consequent_encroachment(self):
        # Bullish FVG between 60,000 (bottom) and 62,000 (top). 50% CE = 61,000
        # Case 1: Candle closes at 61,200 (Above CE -> Valid)
        df_valid = pd.DataFrame({'close': [61500, 61400, 61300, 61250, 61200]})
        self.assertTrue(self.scanner.validate_fvg_consequent_encroachment(df_valid, 62000.0, 60000.0, "LONG"))

        # Case 2: Candle closes at 60,800 (Below CE -> Violated)
        df_breached = pd.DataFrame({'close': [61500, 61400, 61300, 61250, 60800]})
        self.assertFalse(self.scanner.validate_fvg_consequent_encroachment(df_breached, 62000.0, 60000.0, "LONG"))

    def test_order_block_mean_threshold(self):
        # Bullish Order Block: Top = 65,000, Bottom = 64,000. 50% Mean Threshold = 64,500
        # Case 1: Pullback holds above 64,500 -> Valid
        df_valid = pd.DataFrame({'close': [65200, 65000, 64800, 64700, 64600]})
        self.assertTrue(self.scanner.validate_order_block_mean_threshold(df_valid, 65000.0, 64000.0, "LONG"))

        # Case 2: Candle closes at 64,300 (Below MT -> Violated)
        df_breached = pd.DataFrame({'close': [65200, 65000, 64800, 64700, 64300]})
        self.assertFalse(self.scanner.validate_order_block_mean_threshold(df_breached, 65000.0, 64000.0, "LONG"))

    def test_turtle_soup_time_in_zone(self):
        # Swept PDH at 65,000 (SHORT setup)
        # Case 1: Fast sweep: only 2 candles closed above 65,000 before reversing -> Valid
        df_fast = pd.DataFrame({'close': [64800, 64900, 65100, 65050, 64900, 64850, 64800, 64750]})
        self.assertTrue(self.scanner.check_turtle_soup_time_in_zone(df_fast, swept_level=65000.0, direction="SHORT", max_candles=4))

        # Case 2: Prolonged consolidation: 6 candles closed above 65,000 -> True breakout, abort soup
        df_breakout = pd.DataFrame({'close': [65100, 65150, 65200, 65250, 65300, 65350, 65400, 65450]})
        self.assertFalse(self.scanner.check_turtle_soup_time_in_zone(df_breakout, swept_level=65000.0, direction="SHORT", max_candles=4))

if __name__ == '__main__':
    unittest.main()

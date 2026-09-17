import unittest
import pandas as pd
import numpy as np
from src.engines.judas_inducement_engine import JudasInducementEngine

class TestJudasInducementEngine(unittest.TestCase):
    def setUp(self):
        self.engine = JudasInducementEngine(min_wick_pct=70.0, min_atr_mult=1.8, min_vol_mult=1.8)

    def test_bullish_inducement_detection(self):
        """
        Creates a synthetic 5m DataFrame with a violent lower wick (sweeping lows).
        Expects a LONG setup with 3.0R target and tight stop loss.
        """
        data = []
        base_price = 60000.0
        # 25 normal consolidation bars (ATR ~ 50)
        for i in range(25):
            data.append({
                'timestamp': f'2026-08-24 08:{i:02d}:00',
                'open': base_price,
                'high': base_price + 25.0,
                'low': base_price - 25.0,
                'close': base_price + 5.0,
                'volume': 100.0
            })
        
        # Add the Outlier Spike Candle (Range = 200, 4.0x ATR, Lower Wick = 160 = 80%)
        # Open: 60000, Low: 59800, High: 60000, Close: 59960
        # Candle range = 200. Lower wick = 59960 - 59800 = 160 (80% lower wick)
        data.append({
            'timestamp': '2026-08-24 08:26:00',
            'open': 60000.0,
            'high': 60000.0,
            'low': 59800.0,
            'close': 59960.0,
            'volume': 350.0  # 3.5x volume
        })

        df = pd.DataFrame(data)
        setup = self.engine.evaluate_dataframe(df, symbol="BTC/USD")

        self.assertIsNotNone(setup, "Expected Strategy 9 to trigger on 80% lower wick outlier")
        self.assertEqual(setup['direction'], 'LONG')
        self.assertEqual(setup['candle_type'], 'BULLISH_INDUCEMENT_WICK')
        self.assertGreaterEqual(setup['wick_pct'], 70.0)
        self.assertLess(setup['stop_loss'], 59800.0, "Stop loss should be below the spike low")
        self.assertGreater(setup['take_profit'], setup['entry_price'], "Take profit should be higher for LONG")
        
        # Verify 2.5R target ratio
        risk = setup['entry_price'] - setup['stop_loss']
        reward = setup['take_profit'] - setup['entry_price']
        self.assertAlmostEqual(reward / risk, 2.5, delta=0.05)

    def test_bearish_inducement_detection(self):
        """
        Creates a synthetic 5m DataFrame with a violent upper wick (sweeping highs).
        Expects a SHORT setup with 3.0R target and tight stop loss.
        """
        data = []
        base_price = 3000.0
        for i in range(25):
            data.append({
                'timestamp': f'2026-08-24 07:{i:02d}:00',
                'open': base_price,
                'high': base_price + 5.0,
                'low': base_price - 5.0,
                'close': base_price + 1.0,
                'volume': 50.0
            })
        
        # Add the Upper Wick Outlier Spike (Range = 30, 3.0x ATR, Upper Wick = 24 = 80%)
        # Open: 3000, High: 3030, Low: 3000, Close: 3006
        # Upper wick = 3030 - 3006 = 24 (80% upper wick)
        data.append({
            'timestamp': '2026-08-24 07:26:00',
            'open': 3000.0,
            'high': 3030.0,
            'low': 3000.0,
            'close': 3006.0,
            'volume': 150.0  # 3.0x volume
        })


        df = pd.DataFrame(data)
        setup = self.engine.evaluate_dataframe(df, symbol="ETH/USD")

        self.assertIsNotNone(setup, "Expected Strategy 9 to trigger on 80% upper wick outlier")
        self.assertEqual(setup['direction'], 'SHORT')
        self.assertEqual(setup['candle_type'], 'BEARISH_INDUCEMENT_WICK')
        self.assertGreaterEqual(setup['wick_pct'], 70.0)
        self.assertGreater(setup['stop_loss'], 3030.0, "Stop loss should be above the spike high")
        self.assertLess(setup['take_profit'], setup['entry_price'], "Take profit should be lower for SHORT")

    def test_rejection_of_non_outliers(self):
        """
        Normal candle (small wick, normal volume) should return None.
        """
        data = []
        base_price = 60000.0
        for i in range(25):
            data.append({
                'timestamp': f'2026-08-24 00:{i:02d}:00',
                'open': base_price,
                'high': base_price + 20.0,
                'low': base_price - 20.0,
                'close': base_price + 10.0,
                'volume': 100.0
            })
        df = pd.DataFrame(data)
        setup = self.engine.evaluate_dataframe(df, symbol="BTC/USD")
        self.assertIsNone(setup, "Normal consolidation candle should not trigger Strategy 9")

if __name__ == '__main__':
    unittest.main()

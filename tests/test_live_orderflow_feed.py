import time
import json
import unittest
import pandas as pd
from src.engines.live_orderflow_feed import LiveOrderflowFeed, SYMBOL_STREAM_MAP
from src.engines.shadow_substitution_engine import ShadowSubstitutionEngine

class TestLiveOrderflowFeed(unittest.TestCase):
    def setUp(self):
        self.feed = LiveOrderflowFeed()
        with self.feed._data_lock:
            for b in self.feed._buffers.values():
                b.clear()
            for s in self.feed._last_tick_time:
                self.feed._last_tick_time[s] = 0.0

    def test_message_parsing_and_delta(self):
        """Test that Binance aggTrade JSON messages are correctly parsed with buyer/seller delta."""
        # 1. Buyer Maker = True -> Aggressive Seller took liquidity -> Negative Delta
        sell_msg = json.dumps({
            "stream": "btcusdt@aggTrade",
            "data": {
                "e": "aggTrade",
                "E": int(time.time() * 1000),
                "s": "BTCUSDT",
                "p": "77250.00",
                "q": "2.500",
                "T": int(time.time() * 1000),
                "m": True # Buyer was maker -> Taker was Seller
            }
        })
        self.feed._process_message(sell_msg)
        
        # 2. Buyer Maker = False -> Aggressive Buyer took liquidity -> Positive Delta
        buy_msg = json.dumps({
            "stream": "btcusdt@aggTrade",
            "data": {
                "e": "aggTrade",
                "E": int(time.time() * 1000),
                "s": "BTCUSDT",
                "p": "77255.00",
                "q": "4.000",
                "T": int(time.time() * 1000),
                "m": False # Buyer was taker -> Taker was Buyer
            }
        })
        self.feed._process_message(buy_msg)

        metrics = self.feed.get_metrics("BTC/USD", window_seconds=60)
        self.assertTrue(metrics["is_healthy"])
        self.assertAlmostEqual(metrics["cumulative_delta"], 1.500, places=3) # +4.0 - 2.5 = +1.5
        self.assertAlmostEqual(metrics["total_volume"], 6.500, places=3) # 4.0 + 2.5 = 6.5
        self.assertAlmostEqual(metrics["last_price"], 77255.00, places=2)

    def test_ring_buffer_bounded_memory(self):
        """Verify the ring buffer never exceeds maxlen under heavy tick load (memory safety)."""
        now = time.time()
        for i in range(20000):
            msg = json.dumps({
                "stream": "ethusdt@aggTrade",
                "data": {
                    "s": "ETHUSDT",
                    "p": "2500.00",
                    "q": "1.0",
                    "T": int((now + i) * 1000),
                    "m": i % 2 == 0
                }
            })
            self.feed._process_message(msg)

        buffer_len = len(self.feed._buffers["ETH/USD"])
        self.assertLessEqual(buffer_len, 15000)
        self.assertEqual(buffer_len, 15000)

    def test_iceberg_absorption_detection(self):
        """Verify that aggressive selling absorbed by limit buyers triggers Bullish Absorption."""
        now = time.time()
        # Simulate heavy market dumping (20 x 5.0 BTC sell orders = 100 BTC sell volume)
        for i in range(30):
            msg = json.dumps({
                "stream": "btcusdt@aggTrade",
                "data": {
                    "s": "BTCUSDT",
                    "p": "76500.00",
                    "q": "5.0",
                    "T": int(now * 1000),
                    "m": True # Seller market orders
                }
            })
            self.feed._process_message(msg)

        # Price change is flat / positive (e.g. 0.0% change despite heavy dumping)
        is_absorbed, strength, desc = self.feed.evaluate_iceberg_absorption(
            symbol="BTC/USD",
            direction="LONG",
            window_seconds=60,
            price_change_pct=0.0
        )
        self.assertTrue(is_absorbed)
        self.assertGreaterEqual(strength, 0.5)
        self.assertIn("Bullish Absorption", desc)

    def test_shadow_substitution_engine_fallback(self):
        """Verify that ShadowSubstitutionEngine falls back seamlessly to OHLCV proxy if feed is unavailable."""
        engine = ShadowSubstitutionEngine()
        df = pd.DataFrame({
            'open': [76500, 76520, 76510, 76530, 76540, 76520, 76510, 76530, 76550, 76570],
            'high': [76530, 76550, 76540, 76560, 76570, 76550, 76540, 76560, 76580, 76600],
            'low': [76490, 76500, 76500, 76510, 76520, 76500, 76490, 76510, 76530, 76550],
            'close': [76520, 76510, 76530, 76540, 76520, 76510, 76530, 76550, 76570, 76590],
            'volume': [10, 12, 15, 14, 18, 20, 22, 25, 30, 35]
        })
        # Test fallback on untracked asset (e.g. XAU/USD)
        cvd_active, cvd_str, cvd_msg = engine.evaluate_cvd_divergence(df, "LONG", symbol="XAU/USD")
        self.assertIsInstance(cvd_active, bool)
        self.assertIsInstance(cvd_str, float)
        self.assertIsInstance(cvd_msg, str)

if __name__ == "__main__":
    unittest.main()

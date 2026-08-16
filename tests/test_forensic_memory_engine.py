import unittest
import json
from src.engines.retraining_loop import RetrainingLoop
from src.core.memory import SetupMemory

class TestForensicMemoryEngine(unittest.TestCase):
    def setUp(self):
        self.loop = RetrainingLoop()
        self.memory = SetupMemory()

    def test_archetype_classification(self):
        """Verify that trades are correctly classified into the 4 institutional archetypes."""
        # 1. Trend Expansion
        trend_arch = self.loop.classify_trade_archetype(
            pattern="SMC 15m FVG Expansion",
            regime="TRENDING_EXPANSION",
            hurst=0.62,
            symbol="BTC/USD"
        )
        self.assertEqual(trend_arch, "TREND_EXPANSION")

        # 2. Turtle Soup Fader
        fader_arch = self.loop.classify_trade_archetype(
            pattern="Asian EQL Sweep Fader",
            regime="MEAN_REVERTING",
            hurst=0.35,
            symbol="BTC/USD"
        )
        self.assertEqual(fader_arch, "TURTLE_SOUP_FADER")

        # 3. Scalp Velocity
        scalp_arch = self.loop.classify_trade_archetype(
            pattern="Judas Swing Micro-Wick",
            regime="CHOP",
            hurst=0.48,
            symbol="SOL/USD"
        )
        self.assertEqual(scalp_arch, "SCALP_VELOCITY")

        # 4. Core Anchor
        anchor_arch = self.loop.classify_trade_archetype(
            pattern="4H POI Mitigation",
            regime="NEUTRAL",
            hurst=0.50,
            symbol="ETH/USD"
        )
        self.assertEqual(anchor_arch, "CORE_ANCHOR")

    def test_few_shot_building_and_causal_delta(self):
        """Verify that training examples capture visual geometry, market factors, and causal delta."""
        sample_record = {
            'signal_id': 'TEST_SIG_001',
            'timestamp': '2026-08-16T08:15:00Z',
            'symbol': 'BTC/USD',
            'direction': 'BUY',
            'pattern': 'Turtle Soup Asian Sweep',
            'ai_score': 8.5,
            'outcome': 'WIN',
            'pnl': 250.0,
            'shadow_regime': 'MEAN_REVERTING',
            'volume_spike': 1.8,
            'true_smt': '0.52',
            'is_discretionary': 1
        }
        
        example = self.loop._build_few_shot_example(sample_record)
        self.assertEqual(example['archetype'], "TURTLE_SOUP_FADER")
        self.assertEqual(example['outcome'], "WIN")
        self.assertIn("Human Intuition Alpha", example['rule_delta'])
        self.assertAlmostEqual(example['mae_r'], 0.25)
        self.assertAlmostEqual(example['mfe_r'], 2.80)

    def test_textualize_setup(self):
        """Verify that SetupMemory encodes archetype and causal narrative for vector search."""
        setup_dict = {
            'symbol': 'BTC/USD',
            'pattern': 'SMC Bullish Expansion',
            'direction': 'BUY',
            'smt_strength': 0.45,
            'regime': 'TRENDING',
            'hurst': 0.60,
            'time_quartile': {'phase': 'London Open'},
            'news_context': 'Clear'
        }
        narrative = self.memory.textualize_setup(setup_dict)
        self.assertIn("[TREND_EXPANSION]", narrative)
        self.assertIn("London Open", narrative)
        self.assertIn("SMT Confluence: 0.45", narrative)

if __name__ == '__main__':
    unittest.main()

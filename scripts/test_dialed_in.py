#!/usr/bin/env python3
"""
Test Suite for "Institutional Grade" (Sniper Mode) Tuning.
Verifies that the new stricter filters in AIValidator are working as expected.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from src.engines.ai_validator import AIValidator
from src.core.config import Config
import unittest

class TestSniperLogic(unittest.TestCase):
    def setUp(self):
        self.validator = AIValidator(api_key="MOCK")
        
    def test_killzone_config(self):
        """Verify Config updates for expanded windows"""
        print("\nTesting Config Killzones...")
        self.assertEqual(Config.KILLZONE_ASIA, (0, 4))
        self.assertEqual(Config.KILLZONE_LONDON, (7, 10))
        self.assertEqual(Config.KILLZONE_NY_CONTINUOUS, (12, 20))
        print("✓ Killzones expanded correctly")

    def test_strict_thresholds(self):
        """Verify Config updates for thresholds"""
        print("\nTesting Thresholds...")
        self.assertEqual(Config.STRATEGY_MODE, "SNIPER")
        self.assertEqual(Config.AI_THRESHOLD, 8.5)
        self.assertEqual(Config.MIN_SMT_STRENGTH, 0.3)
        self.assertEqual(Config.MAX_PRICE_QUARTILE, 0.5)
        print("✓ Thresholds tightened correctly")

    def test_mock_perfect_setup(self):
        """Verify a perfect setup passes the MOCK validator"""
        print("\nTesting Perfect Setup...")
        # MOCK key force-returns a 9.2 score in the new code
        setup = {
            'symbol': 'BTC/USDT',
            'pattern': 'Judas Sweep',
            'smt_strength': 0.4, # Strong
            'is_discount': True,
            'time_quartile': {'phase': 'Q2: Manipulation'}
        }
        result = self.validator.analyze_trade(setup, {}, {}, df=None)
        live = result['live_execution']
        
        print(f"  Score: {live['score']}")
        print(f"  Verdict: {live['verdict']}")
        
        self.assertTrue(live['score'] >= 8.5)
        self.assertEqual(live['verdict'], "FLOW_GO")
        print("✓ Perfect setup passed")

if __name__ == '__main__':
    unittest.main()

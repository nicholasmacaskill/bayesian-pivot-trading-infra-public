import unittest
from src.engines.champion_challenger_lab import ChampionChallengerLab

class TestChampionChallengerLab(unittest.TestCase):
    def setUp(self):
        self.lab = ChampionChallengerLab()

    def test_variants_initialization(self):
        """Verifies default Champion and Challenger variants are loaded."""
        self.assertIn("STRAT_9_CHAMPION", self.lab.variants)
        self.assertIn("STRAT_9_CHALLENGER", self.lab.variants)
        self.assertIn("STRAT_1_CHAMPION", self.lab.variants)
        self.assertIn("STRAT_1_CHALLENGER", self.lab.variants)
        self.assertEqual(self.lab.variants["STRAT_9_CHAMPION"].variant_type, "CHAMPION")
        self.assertEqual(self.lab.variants["STRAT_9_CHALLENGER"].variant_type, "CHALLENGER")

    def test_record_tournament_outcome(self):
        """Verifies trade results update win rate and profit factor accurately."""
        # Record 4 wins and 1 loss for Strategy 9 Challenger
        for _ in range(4):
            self.lab.record_tournament_outcome("STRAT_9_CHALLENGER", is_win=True, r_mult=2.5)
        self.lab.record_tournament_outcome("STRAT_9_CHALLENGER", is_win=False, r_mult=-1.0)

        v = self.lab.variants["STRAT_9_CHALLENGER"]
        self.assertGreaterEqual(v.samples, 5)
        self.assertEqual(v.wins, 4)
        self.assertEqual(v.losses, 1)
        self.assertEqual(v.win_rate, 80.0)
        self.assertGreater(v.profit_factor, 5.0)

    def test_leaderboard_generation(self):
        """Verifies leaderboard formatting returns valid markdown."""
        table = self.lab.get_tournament_leaderboard()
        self.assertIn("A/B STRATEGY TOURNAMENT LEADERBOARD", table)
        self.assertIn("STRAT_9_CHAMPION", table)
        self.assertIn("LIVE", table)
        self.assertIn("SHADOW", table)

if __name__ == '__main__':
    unittest.main()

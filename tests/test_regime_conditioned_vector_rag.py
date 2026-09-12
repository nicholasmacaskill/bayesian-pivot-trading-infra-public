import unittest
import os
import tempfile
import sqlite3
import numpy as np
from unittest.mock import MagicMock

from src.core.config import Config
from src.engines.visual_vector_engine import VisualVectorEngine
from src.core.memory import SetupMemory
from src.engines.multi_account_funnel import MultiAccountFunnelManager

class TestRegimeConditionedVectorRAG(unittest.TestCase):
    def setUp(self):
        # Create a temporary SQLite database for test isolation
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db_path = self.temp_db.name
        self.temp_db.close()
        
        # Override Config.DB_PATH for isolated testing
        self.orig_db_path = Config.DB_PATH
        Config.DB_PATH = self.db_path
        
        self.vector_engine = VisualVectorEngine(db_path=self.db_path)
        self.funnel_manager = MultiAccountFunnelManager()

    def tearDown(self):
        Config.DB_PATH = self.orig_db_path
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_schema_migration_and_columns(self):
        """Verify that chart_visual_embeddings contains regime_type, hurst, and atr_percentile."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        columns = [row[1] for row in cursor.execute("PRAGMA table_info(chart_visual_embeddings)").fetchall()]
        conn.close()

        self.assertIn("regime_type", columns)
        self.assertIn("hurst", columns)
        self.assertIn("atr_percentile", columns)
        self.assertEqual(self.vector_engine.VECTOR_DIM, 48)

    def test_store_and_prefiltered_vector_search(self):
        """Verify store_embedding stores regime metadata and find_visual_analogs applies pre-filtering."""
        dim = self.vector_engine.VECTOR_DIM
        
        # Create normalized random vectors
        v1 = np.random.randn(dim).astype(np.float32)
        v1 = v1 / np.linalg.norm(v1)

        v2 = np.random.randn(dim).astype(np.float32)
        v2 = v2 / np.linalg.norm(v2)

        # 1. Store 3 embeddings in TRENDING_BULL regime
        for i in range(3):
            stored = self.vector_engine.store_embedding(
                signal_id=f"TB_{i}",
                timestamp=f"2026-09-10T10:0{i}:00Z",
                symbol="BTC/USD",
                pattern="OrderBlock",
                direction="BUY",
                outcome="WIN",
                realized_r=2.5,
                pnl=250.0,
                vector=v1,
                regime_type="TRENDING_BULL",
                hurst=0.65,
                atr_percentile=60.0
            )
            self.assertTrue(stored)

        # 2. Store 1 embedding in CHOPPY regime
        self.vector_engine.store_embedding(
            signal_id="CHOP_0",
            timestamp="2026-09-10T11:00:00Z",
            symbol="BTC/USD",
            pattern="TurtleSoup",
            direction="BUY",
            outcome="LOSS",
            realized_r=-1.0,
            pnl=-100.0,
            vector=v2,
            regime_type="CHOPPY",
            hurst=0.42,
            atr_percentile=40.0
        )

        # Query with regime_type="TRENDING_BULL" (subset >= 3)
        analogs = self.vector_engine.find_visual_analogs(
            query_vector=v1,
            symbol="BTC/USD",
            direction="BUY",
            top_k=3,
            regime_type="TRENDING_BULL"
        )
        self.assertEqual(len(analogs), 3)
        for a in analogs:
            self.assertIn(a["regime_type"], ["TRENDING_BULL", "UNKNOWN"])
            self.assertNotEqual(a["regime_type"], "CHOPPY")

        # Query with regime_type="HIGH_VOL" (0 in DB -> subset < 3 -> graceful fallback to symbol-only)
        fallback_analogs = self.vector_engine.find_visual_analogs(
            query_vector=v1,
            symbol="BTC/USD",
            direction="BUY",
            top_k=4,
            regime_type="HIGH_VOL"
        )
        self.assertEqual(len(fallback_analogs), 4)  # Falls back to symbol-only, returning all 4

    def test_corrective_rag_evaluation_gate(self):
        """Verify SetupMemory.get_context_for_validator filters out low-similarity noise (< 0.72)."""
        memory = SetupMemory()
        
        # Case A: Empty retrieval
        memory.find_similar_setups = MagicMock(return_value=[])
        context_empty = memory.get_context_for_validator({"symbol": "BTC/USD"})
        self.assertEqual(
            context_empty,
            "MEMORY: No statistically valid historical precedents found for this market condition. Evaluate purely on current structural confluence."
        )

        # Case B: Below threshold (< 0.72)
        memory.find_similar_setups = MagicMock(return_value=[
            {"symbol": "BTC/USD", "similarity": 0.68, "pnl": 150.0, "ai_grade": 8.0, "notes": "Weak match"},
            {"symbol": "BTC/USD", "similarity": 0.71, "pnl": -100.0, "ai_score": 6.5, "ai_reasoning": "Marginal match"}
        ])
        context_low_sim = memory.get_context_for_validator({"symbol": "BTC/USD"})
        self.assertEqual(
            context_low_sim,
            "MEMORY: No statistically valid historical precedents found for this market condition. Evaluate purely on current structural confluence."
        )

        # Case C: Above threshold (>= 0.72) with fallback key resolution
        memory.find_similar_setups = MagicMock(return_value=[
            {"symbol": "BTC/USD", "similarity": 0.85, "pnl": 350.0, "ai_grade": 9.0, "notes": "Verified winner"},
            {"symbol": "BTC/USD", "similarity": 0.74, "pnl": -80.0, "ai_score": 7.0, "ai_reasoning": "Fallback reasoning test"},
            {"symbol": "BTC/USD", "similarity": 0.55, "pnl": 200.0, "ai_score": 7.5, "notes": "Low sim noise ignored"}
        ])
        context_valid = memory.get_context_for_validator({"symbol": "BTC/USD"})
        self.assertIn("MEMORY: Found similar historical setups:", context_valid)
        self.assertIn("Result: WIN ($350.0)", context_valid)
        self.assertIn("AI Grade: 9.0/10", context_valid)
        self.assertIn("Feedback: Verified winner", context_valid)
        self.assertIn("Result: LOSS ($-80.0)", context_valid)
        self.assertIn("AI Grade: 7.0/10", context_valid)
        self.assertIn("Feedback: Fallback reasoning test", context_valid)
        self.assertNotIn("Low sim noise ignored", context_valid)

    def test_multi_account_funnel_wiring(self):
        """Verify MultiAccountFunnelManager supports candidate visual analogs conditioned on regime."""
        dim = self.vector_engine.VECTOR_DIM
        v = np.random.randn(dim).astype(np.float32)
        v = v / np.linalg.norm(v)
        
        self.vector_engine.store_embedding(
            signal_id="TEST_FUNNEL",
            timestamp="2026-09-10T12:00:00Z",
            symbol="ETH/USD",
            pattern="FVG",
            direction="BUY",
            outcome="WIN",
            realized_r=2.0,
            pnl=200.0,
            vector=v,
            regime_type="TRENDING_BULL"
        )

        candidate = {
            "symbol": "ETH/USD",
            "direction": "BUY",
            "pattern": "FVG",
            "regime": "TRENDING_BULL",
            "hurst": 0.60
        }

        # Query candidate analogs via funnel manager
        analogs = self.funnel_manager.find_candidate_visual_analogs(
            candidate_setup=candidate,
            query_vector=v,
            regime_type="TRENDING_BULL"
        )
        self.assertGreaterEqual(len(analogs), 1)
        self.assertEqual(analogs[0]["symbol"], "ETH/USD")
        self.assertEqual(analogs[0]["regime_type"], "TRENDING_BULL")

        # Eligibility check accepts regime_type
        passed, reasons = self.funnel_manager.evaluate_setup_for_account(
            setup=candidate,
            account_key="ACCOUNT_A",
            hurst=0.60,
            regime_allowed=True,
            regime_type="TRENDING_BULL"
        )
        self.assertTrue(passed)

if __name__ == '__main__':
    unittest.main()

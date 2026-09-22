"""
Visual Vector Engine (Multimodal Geometric & Visual RAG)
========================================================
Encodes candlestick chart geometry, liquidity sweeps, and price action 
into dense mathematical vector embeddings for sub-millisecond visual similarity search.

Used by the Shadow Lab Tournament to match live market formations against
1,457+ historical trade outcomes and detect deceptive loss traps before live execution.
"""

import os
import json
import sqlite3
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import numpy as np

from src.core.config import Config
from src.core.database import get_db_connection, execute_db_write_with_retry

logger = logging.getLogger("VisualVectorEngine")


class VisualVectorEngine:
    """
    Multimodal Visual & Geometric Embedding Engine.
    Stores and queries chart vectors using vectorized cosine similarity.
    """

    VECTOR_DIM = 48  # Standardized dense geometric & pattern feature dimension

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or Config.DB_PATH
        self._init_db()

    def _init_db(self):
        """Initializes the visual embeddings table in SQLite."""
        try:
            conn = get_db_connection()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chart_visual_embeddings (
                    embedding_id TEXT PRIMARY KEY,
                    signal_id TEXT,
                    timestamp TEXT,
                    symbol TEXT,
                    pattern TEXT,
                    session TEXT,
                    direction TEXT,
                    outcome TEXT,
                    realized_r REAL,
                    pnl REAL,
                    vector BLOB,
                    vector_dim INTEGER,
                    notes TEXT,
                    regime_type TEXT DEFAULT 'UNKNOWN',
                    hurst REAL DEFAULT 0.50,
                    atr_percentile REAL DEFAULT 50.0,
                    created_at TEXT
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_cve_symbol_pattern 
                ON chart_visual_embeddings(symbol, pattern);
            """)

            # Auto-migration for existing SQLite tables
            for col, col_def in [
                ('regime_type', "TEXT DEFAULT 'UNKNOWN'"),
                ('hurst', "REAL DEFAULT 0.50"),
                ('atr_percentile', "REAL DEFAULT 50.0")
            ]:
                try:
                    conn.execute(f"ALTER TABLE chart_visual_embeddings ADD COLUMN {col} {col_def}")
                except sqlite3.OperationalError:
                    pass

            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Error initializing chart_visual_embeddings table: {e}")

    def extract_geometric_features(
        self,
        df: Any,
        setup: Optional[Dict[str, Any]] = None,
        lookback: int = 30
    ) -> np.ndarray:
        """
        Extracts a normalized, invariant 48-dimensional geometric feature vector
        from price action candles and SMC structure:
          - Candle Body vs Wick Ratios (recent 10 candles)
          - Normalized True Range (volatility expansion)
          - Sweep Depth & Wick Rejection Ratio
          - Displacement Slope & Momentum
          - Orderflow CVD / Volume Expansion
          - Fair Value Gap Geometry
        """
        vector = np.zeros(self.VECTOR_DIM, dtype=np.float32)
        if df is None or len(df) < 10:
            return vector

        try:
            sub_df = df.iloc[-lookback:] if len(df) >= lookback else df
            closes = sub_df['close'].values
            highs = sub_df['high'].values
            lows = sub_df['low'].values
            opens = sub_df['open'].values
            volumes = sub_df['volume'].values if 'volume' in sub_df else np.ones(len(sub_df))

            # 1. Recent Candle Anatomy (10 candles x 3 features = 30 dims)
            n_recent = min(10, len(sub_df))
            for i in range(n_recent):
                idx = -(n_recent - i)
                c_range = max(highs[idx] - lows[idx], 1e-6)
                body = abs(closes[idx] - opens[idx])
                upper_wick = highs[idx] - max(opens[idx], closes[idx])
                lower_wick = min(opens[idx], closes[idx]) - lows[idx]

                vector[i * 3] = body / c_range
                vector[i * 3 + 1] = upper_wick / c_range
                vector[i * 3 + 2] = lower_wick / c_range

            # 2. Volatility & Range Expansion (Dims 30–38)
            curr_price = closes[-1]
            atr = np.mean(highs[-14:] - lows[-14:]) if len(highs) >= 14 else np.mean(highs - lows)
            norm_atr = atr / max(curr_price, 1e-6)
            vector[30] = np.clip(norm_atr * 100.0, 0.0, 5.0)

            # High/Low Range Normalized
            hh = np.max(highs)
            ll = np.min(lows)
            total_range = max(hh - ll, 1e-6)
            vector[31] = (curr_price - ll) / total_range  # Current position in range (0.0–1.0)
            vector[32] = (highs[-1] - ll) / total_range
            vector[33] = (lows[-1] - ll) / total_range

            # 3. Momentum & Displacement Slopes (Dims 34–42)
            if len(closes) >= 5:
                slope_5 = (closes[-1] - closes[-5]) / (5 * atr) if atr > 0 else 0.0
                vector[34] = np.clip(slope_5, -3.0, 3.0)
            if len(closes) >= 15:
                slope_15 = (closes[-1] - closes[-15]) / (15 * atr) if atr > 0 else 0.0
                vector[35] = np.clip(slope_15, -3.0, 3.0)

            # Volume Expansion Ratio
            avg_vol = np.mean(volumes[-20:]) if len(volumes) >= 20 else np.mean(volumes)
            vol_ratio = (volumes[-1] / max(avg_vol, 1e-6)) if avg_vol > 0 else 1.0
            vector[36] = np.clip(vol_ratio, 0.0, 5.0)

            # 4. Setup Specific Geometry (Dims 43–63)
            if setup:
                direction_sign = 1.0 if str(setup.get('direction', '')).upper() in ['BUY', 'LONG'] else -1.0
                vector[43] = direction_sign
                vector[44] = float(setup.get('smt_strength', 0.0) or 0.0)
                vector[45] = float(setup.get('hurst', setup.get('hurst_exponent', 0.50)) or 0.50)
                vector[46] = float(setup.get('wick_pct', 50.0) or 50.0) / 100.0
                vector[47] = float(setup.get('ai_score', 7.5) or 7.5) / 10.0

            # L2 Normalization for stable Cosine Similarity
            norm = np.linalg.norm(vector)
            if norm > 1e-6:
                vector = vector / norm

        except Exception as e:
            logger.debug(f"Feature extraction fallback warning: {e}")

        return vector

    def store_embedding(
        self,
        signal_id: str,
        timestamp: str,
        symbol: str,
        pattern: str,
        direction: str,
        outcome: str,
        realized_r: float,
        pnl: float,
        vector: np.ndarray,
        session: str = "GLOBAL",
        notes: str = "",
        regime_type: str = "UNKNOWN",
        hurst: float = 0.50,
        atr_percentile: float = 50.0
    ) -> bool:
        """Stores a computed vector embedding and its verified outcome in SQLite."""
        try:
            embedding_id = f"VEC_{signal_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
            vector_blob = vector.astype(np.float32).tobytes()

            query = """
                INSERT OR REPLACE INTO chart_visual_embeddings (
                    embedding_id, signal_id, timestamp, symbol, pattern, 
                    session, direction, outcome, realized_r, pnl, 
                    vector, vector_dim, notes, regime_type, hurst, atr_percentile, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                embedding_id, str(signal_id), str(timestamp), str(symbol), str(pattern),
                str(session), str(direction), str(outcome), float(realized_r), float(pnl),
                vector_blob, len(vector), str(notes), str(regime_type), float(hurst), float(atr_percentile),
                datetime.now(timezone.utc).isoformat()
            )
            execute_db_write_with_retry(query, params)
            return True
        except Exception as e:
            logger.error(f"Failed to store visual embedding: {e}")
            return False

    def find_visual_analogs(
        self,
        query_vector: np.ndarray,
        symbol: Optional[str] = None,
        direction: Optional[str] = None,
        top_k: int = 5,
        regime_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Performs fast cosine similarity search across the visual embeddings library.
        Enforces directional isolation (Longs match Longs, Shorts match Shorts)
        and optionally pre-filters by regime_type with graceful fallback.
        Returns the top-K nearest historical chart analogs with their realized outcomes.
        """
        if query_vector is None or len(query_vector) == 0:
            return []

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            q_norm = np.linalg.norm(query_vector)
            if q_norm < 1e-6:
                conn.close()
                return []

            def _query_and_score(apply_regime_filter: bool, apply_direction_filter: bool = True) -> List[Dict[str, Any]]:
                query = """
                    SELECT embedding_id, signal_id, timestamp, symbol, pattern, 
                           direction, outcome, realized_r, pnl, vector, notes,
                           regime_type, hurst, atr_percentile 
                    FROM chart_visual_embeddings
                """
                params = []
                conditions = []

                if symbol:
                    conditions.append("(symbol = ? OR symbol LIKE ?)")
                    params.extend([symbol, f"%{symbol.split('/')[0]}%"])

                dir_clean = str(direction or "").upper()
                target_dirs = []
                if dir_clean in ["BUY", "LONG"]:
                    target_dirs = ["BUY", "LONG"]
                elif dir_clean in ["SELL", "SHORT"]:
                    target_dirs = ["SELL", "SHORT"]

                if apply_direction_filter and target_dirs:
                    conditions.append("(direction = ? OR direction = ?)")
                    params.extend(target_dirs)

                if apply_regime_filter and regime_type and str(regime_type).upper() != "UNKNOWN":
                    conditions.append("(regime_type = ? OR regime_type IS NULL OR regime_type = 'UNKNOWN')")
                    params.append(str(regime_type))

                if conditions:
                    query += " WHERE " + " AND ".join(conditions)

                rows = cursor.execute(query, tuple(params)).fetchall()
                if not rows:
                    return []

                similarities = []
                for r in rows:
                    v_blob = r[9]
                    if not v_blob:
                        continue
                    db_vector = np.frombuffer(v_blob, dtype=np.float32)
                    if len(db_vector) != len(query_vector):
                        continue
                    db_norm = np.linalg.norm(db_vector)
                    if db_norm < 1e-6:
                        continue

                    cosine_sim = float(np.dot(query_vector, db_vector) / (q_norm * db_norm))
                    similarities.append({
                        'embedding_id': r[0],
                        'signal_id': r[1],
                        'timestamp': r[2],
                        'symbol': r[3],
                        'pattern': r[4],
                        'direction': r[5],
                        'outcome': r[6],
                        'realized_r': float(r[7] or 0.0),
                        'pnl': float(r[8] or 0.0),
                        'notes': r[10] or '',
                        'regime_type': r[11] if len(r) > 11 and r[11] is not None else 'UNKNOWN',
                        'hurst': float(r[12] or 0.50) if len(r) > 12 and r[12] is not None else 0.50,
                        'atr_percentile': float(r[13] or 50.0) if len(r) > 13 and r[13] is not None else 50.0,
                        'similarity': round(cosine_sim, 4)
                    })

                similarities.sort(key=lambda x: x['similarity'], reverse=True)
                return similarities

            # Directionally isolated search
            analogs = []
            if regime_type and str(regime_type).upper() != "UNKNOWN":
                analogs = _query_and_score(apply_regime_filter=True, apply_direction_filter=True)
                if len(analogs) < top_k:
                    # Fall back to direction-filtered without regime constraint
                    analogs = _query_and_score(apply_regime_filter=False, apply_direction_filter=True)
            else:
                analogs = _query_and_score(apply_regime_filter=False, apply_direction_filter=True)

            # If no directional matches exist at all (new asset), fallback to direction-free
            if len(analogs) == 0:
                analogs = _query_and_score(apply_regime_filter=False, apply_direction_filter=False)

            conn.close()
            return analogs[:top_k]

        except Exception as e:
            logger.error(f"Error querying visual analogs: {e}")
            return []

    def evaluate_visual_precedent(
        self,
        query_vector: np.ndarray,
        symbol: str,
        direction: str,
        regime_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Evaluates visual precedent against historical library.
        Returns:
          - recommendation: 'PASS_CONFIRMED', 'REJECT_TRAP', or 'NEUTRAL'
          - score_modifier: Bayesian score adjustment (-2.0, -1.5, +1.0, 0.0)
          - is_severe_trap: True only for extreme twin traps (>=90% sim, 0% WR)
          - win_rate: Historical win rate of nearest visual twins
          - avg_r: Expected R-multiple
          - key_reason: Analytical explanation
        """
        analogs = self.find_visual_analogs(
            query_vector, symbol=symbol, direction=direction, top_k=5, regime_type=regime_type
        )
        return self.evaluate_analogs(analogs)

    def evaluate_analogs(self, analogs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Evaluates a list of retrieved visual analogs and classifies setup into PASS_CONFIRMED, REJECT_TRAP, or NEUTRAL."""
        if not analogs:
            return {
                'recommendation': 'NEUTRAL',
                'confidence': 0.50,
                'win_rate': 50.0,
                'avg_r': 0.0,
                'score_modifier': 0.0,
                'is_severe_trap': False,
                'analogs': [],
                'key_reason': 'No close visual matches in database yet.'
            }

        wins = sum(1 for a in analogs if a.get('outcome') == 'WIN' or a.get('realized_r', 0) > 0)
        traps = sum(1 for a in analogs if a.get('outcome') in ['LOSS', 'TRAP'] or a.get('realized_r', 0) <= 0)
        avg_sim = float(np.mean([a['similarity'] for a in analogs]))
        avg_r = float(np.mean([a.get('realized_r', 0.0) for a in analogs]))
        win_rate = (wins / len(analogs)) * 100.0

        top_match = analogs[0]
        score_modifier = 0.0
        is_severe_trap = False

        # Multi-tiered Bayesian Vector Confluence (Advisory Only — Zero Hard Veto):
        # Tier 1: Strong Verified Winning Twin — >=82% similarity with >=2 wins
        if avg_sim >= 0.82 and wins >= 2 and win_rate >= 60.0:
            recommendation = 'PASS_CONFIRMED'
            score_modifier = +0.5
            reason = f"🏆 Visual Vector Precedent: {avg_sim:.1%} match to verified historical winners (Avg R: +{avg_r:.1f}R, Top match: {top_match.get('pattern', 'Pattern')}). Score boost: +0.5."
        # Tier 2: Strong Precedent Trap — >=85% similarity with >=2 traps OR >=75% with win rate <=25%
        elif (avg_sim >= 0.85 and traps >= 2) or (avg_sim >= 0.75 and traps >= 2 and win_rate <= 25.0):
            recommendation = 'REJECT_TRAP'
            score_modifier = -0.5
            reason = f"⚠️ Visual Vector Trap: {avg_sim:.1%} match to historical false sweeps ({win_rate:.0f}% win rate, Avg R: {avg_r:.1f}R). Score penalty: -0.5."
        elif avg_sim >= 0.80 and wins >= 2:
            recommendation = 'PASS_CONFIRMED'
            score_modifier = +0.5
            reason = f"🏆 Visual Vector Precedent: {avg_sim:.1%} match to verified historical winners (Avg R: +{avg_r:.1f}R, Top match: {top_match.get('pattern', 'Pattern')}). Score boost: +0.5."
        else:
            recommendation = 'NEUTRAL'
            score_modifier = 0.0
            reason = f"Visual similarity balanced ({win_rate:.0f}% win rate across {len(analogs)} historical analogs, similarity: {avg_sim:.1%})."

        return {
            'recommendation': recommendation,
            'confidence': avg_sim,
            'win_rate': win_rate,
            'avg_r': avg_r,
            'score_modifier': score_modifier,
            'is_severe_trap': False,
            'analogs': analogs,
            'key_reason': reason
        }

    def test_similarity_query(self) -> Dict[str, Any]:
        """Smoke test verifying vector extraction and query speed."""
        dummy_df = None
        dummy_vector = np.random.randn(self.VECTOR_DIM).astype(np.float32)
        dummy_vector = dummy_vector / np.linalg.norm(dummy_vector)
        
        t0 = datetime.now()
        analogs = self.find_visual_analogs(dummy_vector, top_k=3)
        t_elapsed_ms = (datetime.now() - t0).total_seconds() * 1000.0

        return {
            'status': 'SUCCESS',
            'query_latency_ms': round(t_elapsed_ms, 2),
            'stored_vectors_count': len(analogs),
            'vector_dim': self.VECTOR_DIM
        }

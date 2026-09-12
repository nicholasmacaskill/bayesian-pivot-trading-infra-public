import os
import json
import time
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

MAP_FILE_PATH = "/tmp/sovereign_ai_permission_map.json"

class AIPermissionMap:
    """
    Asynchronous In-Memory AI Permission & RAG Knowledge Map.
    
    Provides sub-millisecond (<0.5ms) lookup of macro AI bias, RAG historical 
    similarity, and permitted archetypes for fast-lane deterministic execution engines.
    """
    _cache: Dict[str, Any] = {}
    _last_read_ts: float = 0.0

    @classmethod
    def set_permission(
        cls, 
        symbol: str, 
        ai_bias: str, 
        conviction_score: float, 
        regime: str, 
        rag_similarity: float = 0.0,
        authorized_archetypes: list = None,
        notes: str = ""
    ) -> None:
        """
        Called by the 1H/4H AI Validator / RAG Engine to publish pre-computed macro intelligence.
        """
        data = cls._read_file()
        data[symbol] = {
            "symbol": symbol,
            "timestamp": time.time(),
            "ai_bias": ai_bias, # "BULLISH", "BEARISH", "NEUTRAL"
            "conviction_score": round(float(conviction_score), 2),
            "regime": regime,
            "rag_similarity": round(float(rag_similarity), 2),
            "authorized_archetypes": authorized_archetypes or ["TURTLE_SOUP_LIQUIDITY_SWEEP", "LONDON_CLOSE_SILVER_BULLET"],
            "notes": notes
        }
        cls._write_file(data)
        cls._cache = data
        cls._last_read_ts = time.time()
        logger.info(f"🧠 [AI Permission Map] Updated {symbol}: Bias={ai_bias} | Conviction={conviction_score}/10 | RAG={rag_similarity}%")

    @classmethod
    def get_permission(cls, symbol: str) -> Dict[str, Any]:
        """
        Ultra-fast (<0.5ms) zero-latency lookup for real-time 5m execution engines.
        """
        now = time.time()
        if now - cls._last_read_ts > 10.0 or not cls._cache:
            cls._cache = cls._read_file()
            cls._last_read_ts = now

        entry = cls._cache.get(symbol)
        if not entry:
            # Default safe baseline if no 1H AI update exists yet
            return {
                "symbol": symbol,
                "timestamp": now,
                "ai_bias": "NEUTRAL",
                "conviction_score": 7.5,
                "regime": "MEAN_REVERSION",
                "rag_similarity": 50.0,
                "authorized_archetypes": ["TURTLE_SOUP_LIQUIDITY_SWEEP", "LONDON_CLOSE_SILVER_BULLET"],
                "notes": "Default baseline permission"
            }
            
        # Check if entry is older than 4 hours (stale safeguard)
        if now - entry.get("timestamp", 0) > 14400:
            entry["is_stale"] = True
        else:
            entry["is_stale"] = False
            
        return entry

    @classmethod
    def evaluate_confluence(cls, symbol: str, direction: str, pattern_type: str) -> tuple[bool, float, str]:
        """
        Evaluates real-time 5m setup against pre-computed 1H AI RAG state.
        Returns: (is_approved, dynamic_risk_multiplier, reason_msg)
        """
        perm = cls.get_permission(symbol)
        bias = perm.get("ai_bias", "NEUTRAL")
        conviction = perm.get("conviction_score", 7.5)
        rag_sim = perm.get("rag_similarity", 50.0)
        auth_archetypes = perm.get("authorized_archetypes", [])

        if perm.get("is_stale"):
            return False, 0.0, "AI Permission is STALE (older than 4 hours). Execution blocked."

        # 1. Archetype Authorization
        if pattern_type not in auth_archetypes:
            return False, 0.0, f"Archetype {pattern_type} not in authorized list {auth_archetypes}"

        # 2. Bias Alignment Check
        is_aligned = (
            (bias == "BULLISH" and direction in ("BUY", "LONG")) or
            (bias == "BEARISH" and direction in ("SELL", "SHORT")) or
            bias == "NEUTRAL"
        )
        
        is_hard_counter = (
            (bias == "BULLISH" and direction in ("SELL", "SHORT") and conviction >= 8.5) or
            (bias == "BEARISH" and direction in ("BUY", "LONG") and conviction >= 8.5)
        )

        if is_hard_counter:
            return False, 0.0, f"Hard conflict with 1H AI Macro Bias ({bias}, Conviction {conviction}/10)"

        # 3. Dynamic Sizing Multiplier (Asymmetric Risk)
        if is_aligned and conviction >= 8.5 and rag_sim >= 70.0:
            risk_mult = 1.0  # High-conviction full allocation
            msg = f"Full High-Alpha Confluence (AI: {conviction}/10, RAG: {rag_sim}%, Bias: {bias})"
        elif is_aligned:
            risk_mult = 0.5  # Standard probe size
            msg = f"Standard Confluence (AI: {conviction}/10, Bias: {bias})"
        else:
            risk_mult = 0.25 # Soft counter-bias cautious probe
            msg = f"Soft Counter-Bias Probe (AI Bias: {bias})"

        return True, risk_mult, msg

    @classmethod
    def _read_file(cls) -> Dict[str, Any]:
        if not os.path.exists(MAP_FILE_PATH):
            return {}
        try:
            with open(MAP_FILE_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    @classmethod
    def _write_file(cls, data: Dict[str, Any]) -> None:
        try:
            with open(MAP_FILE_PATH, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to persist AI permission map: {e}")

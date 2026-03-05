"""
Correlation Risk Gate
=====================
Prevents triple-correlated blowup by tracking directional exposure across
open + pending signals.

Rules:
  - BTC, ETH, SOL are treated as a correlated basket (crypto beta).
  - Max 1 active LONG signal and 1 active SHORT signal per basket.
  - A new signal in the same direction as 2+ existing exposures is BLOCKED.
  - Tracks signal IDs so it can release slots when trades close.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Asset groups treated as correlated baskets
CORRELATION_BASKETS = {
    "CRYPTO_MAJOR": ["BTC/USD", "ETH/USD", "SOL/USD"],
    "CRYPTO_ALT":   ["AVAX/USD", "LINK/USD", "MATIC/USD"],
}

# Max concurrent signals in the SAME direction per basket
MAX_CORRELATED_SIGNALS = 1  # Allow max 1 long AND 1 short at a time per basket


class CorrelationGate:
    """
    Enforces a portfolio-level correlation limit on concurrent signals.

    Usage:
        gate = CorrelationGate()
        allowed, reason = gate.check(symbol, direction, signal_id)
        if not allowed:
            logger.warning(f"CORRELATION BLOCKED: {reason}")
            return None
        # ... proceed to alert
        gate.register(signal_id, symbol, direction)
        # ... when trade closes
        gate.release(signal_id)
    """

    def __init__(self, max_per_direction: int = MAX_CORRELATED_SIGNALS, expiry_hours: float = 4.0):
        # Active signals: {signal_id: {symbol, direction, basket, expires_at}}
        self._active: dict[str, dict] = {}
        self.max_per_direction = max_per_direction
        self.expiry_hours = expiry_hours  # Auto-expire slots after N hours (safety valve)

    def _basket_for(self, symbol: str) -> Optional[str]:
        """Returns the basket name for a given symbol, or None if no basket."""
        for basket, members in CORRELATION_BASKETS.items():
            if symbol in members:
                return basket
        return None

    def _purge_expired(self):
        """Remove signals that have been active past their TTL."""
        now = datetime.now(timezone.utc)
        expired = [sid for sid, s in self._active.items() if s['expires_at'] < now]
        for sid in expired:
            logger.debug(f"[CorrelationGate] Auto-expiring slot for signal {sid} ({self._active[sid]['symbol']})")
            del self._active[sid]

    def check(self, symbol: str, direction: str) -> tuple[bool, str]:
        """
        Returns (allowed: bool, reason: str).
        Call this BEFORE registering a new signal.
        """
        self._purge_expired()

        basket = self._basket_for(symbol)
        if basket is None:
            return True, "No basket — uncorrelated asset, pass."

        # Count active signals in same basket + same direction
        same_dir = [
            s for s in self._active.values()
            if s['basket'] == basket
            and s['direction'].upper() == direction.upper()
            and s['symbol'] != symbol  # Don't count the same symbol twice
        ]

        if len(same_dir) >= self.max_per_direction:
            symbols_held = [s['symbol'] for s in same_dir]
            reason = (
                f"CORRELATION LIMIT: Already holding {len(same_dir)} {direction} "
                f"signal(s) in {basket} basket ({', '.join(symbols_held)}). "
                f"Adding {symbol} would create correlated exposure ≥ {self.max_per_direction + 1}."
            )
            logger.warning(f"🛑 [CorrelationGate] {reason}")
            return False, reason

        return True, f"OK — {len(same_dir)} existing {direction} signal(s) in {basket}."

    def register(self, signal_id: str, symbol: str, direction: str):
        """Register a new active signal slot after it passes the gate."""
        basket = self._basket_for(symbol)
        if basket is None:
            return  # Uncorrelated, no slot needed

        self._active[signal_id] = {
            'symbol': symbol,
            'direction': direction.upper(),
            'basket': basket,
            'registered_at': datetime.now(timezone.utc),
            'expires_at': datetime.now(timezone.utc) + timedelta(hours=self.expiry_hours),
        }
        logger.info(
            f"[CorrelationGate] Registered {direction} slot for {symbol} "
            f"(ID: {signal_id}, basket: {basket}). "
            f"Active slots: {len(self._active)}"
        )

    def release(self, signal_id: str):
        """Release a slot when a trade closes (called from journal sync)."""
        if signal_id in self._active:
            s = self._active.pop(signal_id)
            logger.info(f"[CorrelationGate] Released {s['direction']} slot for {s['symbol']} (ID: {signal_id})")

    def get_status(self) -> dict:
        """Returns a summary of current correlation exposure."""
        self._purge_expired()
        summary = {}
        for basket in CORRELATION_BASKETS:
            longs = [s['symbol'] for s in self._active.values() if s['basket'] == basket and s['direction'] == 'LONG']
            shorts = [s['symbol'] for s in self._active.values() if s['basket'] == basket and s['direction'] == 'SHORT']
            summary[basket] = {'LONG': longs, 'SHORT': shorts}
        return summary

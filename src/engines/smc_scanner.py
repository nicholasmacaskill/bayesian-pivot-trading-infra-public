"""
SMC Scanner — Sovereign Edge Engine
====================================
Detects Smart Money Concepts (SMC) formations across multiple timeframes.

Core capabilities (implementation is private):
  - Order Block detection (Bullish / Bearish)
  - Fair Value Gap (FVG) classification
  - Inducement & Liquidity Sweep identification
  - Break of Structure (BOS) and Change of Character (CHoCH) labelling
  - 4H bias determination via EMA-based market structure
  - Session-quartile-aware entry timing
  - SMT (Smart Money Tool) divergence scoring against correlated assets

For research enquiries contact: research@yourdomain.com
"""

from abc import ABC, abstractmethod


class BaseSMCScanner(ABC):
    """Abstract base class for SMC scanner implementations."""

    @abstractmethod
    def fetch_data(self, symbol: str, timeframe: str, limit: int = 200):
        """Fetch OHLCV data for a given symbol and timeframe."""
        ...

    @abstractmethod
    def detect_patterns(self, symbol: str) -> list[dict]:
        """
        Detect all SMC formations for a symbol.

        Returns a list of signal dicts, each containing:
          - pattern   (str)  : Formation name
          - direction (str)  : 'LONG' | 'SHORT'
          - level     (float): Key price level
          - score     (float): Raw confluence score (0–10)
        """
        ...

    @abstractmethod
    def get_detailed_bias(self, symbol: str, index_context: dict = None) -> str:
        """Return a human-readable 4H bias label for the given symbol."""
        ...

    @abstractmethod
    def get_hurst_exponent(self, closes) -> float:
        """Compute the Hurst Exponent from a close-price series."""
        ...

    @abstractmethod
    def get_adf_test(self, closes) -> float:
        """Return the ADF p-value for stationarity testing."""
        ...

    @abstractmethod
    def get_session_quartile(self) -> dict:
        """Return the current session quartile info (phase, mins_remaining)."""
        ...

    @abstractmethod
    def detect_htf_pois(self, symbol: str) -> list[dict]:
        """
        Detect Higher-Timeframe Points of Interest (POIs) for a symbol.

        Returns a list of dicts, each containing:
          - level (float): Price level
          - type  (str)  : 'OB' | 'FVG' | 'EQL'
        """
        ...

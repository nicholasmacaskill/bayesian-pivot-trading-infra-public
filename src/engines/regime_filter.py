"""
Regime Detection Filter
=======================
Classifies the current market regime before allowing a signal through.

The same ICT pattern in different regimes has completely different expectancy:
  - TRENDING:    Order blocks / CHoCH have high follow-through. ✅ Trade.
  - RANGING:     Turtle Soups (liquidity sweeps) work well.    ✅ Trade (sweeps only).
  - CHOPPY:      No edge. All patterns break down.             ❌ Block.
  - HIGH_VOL:    Spikes exceed stops. ATR-adjusted sizing.     ⚠️ Warn + size down.

Detection Methods:
  1. Hurst Exponent  — H > 0.55 = Trending, H < 0.45 = Mean-Reverting
  2. ATR Percentile  — ATR vs 90-day distribution (volatility regime)
  3. EMA Alignment   — 20/50/200 stack = directional conviction
  4. ADX             — > 25 = trending, < 20 = ranging/choppy
"""

import logging
import numpy as np
import pandas as pd
from enum import Enum
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


class Regime(str, Enum):
    TRENDING_BULL  = "TRENDING_BULL"
    TRENDING_BEAR  = "TRENDING_BEAR"
    RANGING        = "RANGING"
    CHOPPY         = "CHOPPY"
    HIGH_VOL       = "HIGH_VOL"
    UNKNOWN        = "UNKNOWN"


@dataclass
class RegimeResult:
    regime: Regime
    allowed: bool
    confidence: float        # 0.0–1.0
    reason: str
    adx: float
    hurst: float
    atr_pct: float           # ATR as % of price
    atr_percentile: float    # Where current ATR sits vs 90-day history (0–100)
    suggested_size_mult: float  # 1.0 = normal, 0.5 = half size, etc.

    def __str__(self):
        return (
            f"Regime: {self.regime.value} | "
            f"Confidence: {self.confidence:.0%} | "
            f"ADX: {self.adx:.1f} | "
            f"Hurst: {self.hurst:.2f} | "
            f"ATR%ile: {self.atr_percentile:.0f} | "
            f"SizeMult: {self.suggested_size_mult:.1f}x"
        )


class RegimeFilter:
    """
    Classifies market regime and returns a trade permission + sizing multiplier.

    Usage:
        rf = RegimeFilter()
        result = rf.classify(symbol, df_1h, df_5m)
        if not result.allowed:
            logger.warning(f"REGIME BLOCKED: {result.reason}")
            return None
        risk_mult = result.suggested_size_mult
    """

    def __init__(self):
        # Per-symbol ATR history for percentile calculation
        self._atr_history: dict[str, list[float]] = {}

    # ──────────────────────────────────────────────────────────────────────────
    # Internal Indicators
    # ──────────────────────────────────────────────────────────────────────────

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        tr = pd.concat([
            df['high'] - df['low'],
            (df['high'] - df['close'].shift()).abs(),
            (df['low']  - df['close'].shift()).abs(),
        ], axis=1).max(axis=1)
        return tr.rolling(period).mean()

    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> float:
        """Average Directional Index — measures trend strength (not direction)."""
        try:
            high  = df['high']
            low   = df['low']
            close = df['close']

            plus_dm  = high.diff()
            minus_dm = -low.diff()
            plus_dm[plus_dm  < 0] = 0
            minus_dm[minus_dm < 0] = 0

            tr  = self._calculate_atr(df, period)
            plus_di  = 100 * (plus_dm.rolling(period).mean()  / tr)
            minus_di = 100 * (minus_dm.rolling(period).mean() / tr)

            dx  = (100 * (plus_di - minus_di).abs() / (plus_di + minus_di + 1e-9))
            adx = dx.rolling(period).mean().iloc[-1]
            return float(adx) if not np.isnan(adx) else 20.0
        except Exception as e:
            logger.debug(f"ADX calculation failed: {e}")
            return 20.0

    def _calculate_hurst(self, series: np.ndarray) -> float:
        """
        Hurst Exponent via R/S analysis.
        H > 0.55 = trending / persistent
        H < 0.45 = mean-reverting
        H ≈ 0.5  = random walk
        """
        try:
            lags   = range(2, min(20, len(series) // 4))
            tau    = [np.sqrt(np.std(np.subtract(series[lag:], series[:-lag]))) for lag in lags]
            log_lags = np.log(list(lags))
            log_tau  = np.log(tau)
            poly = np.polyfit(log_lags, log_tau, 1)
            return float(poly[0] * 2.0)
        except Exception:
            return 0.5

    def _ema_alignment(self, df: pd.DataFrame) -> int:
        """
        Returns +1 (bullish stack), -1 (bearish stack), 0 (mixed).
        20 > 50 > 200 EMA = bullish; 20 < 50 < 200 = bearish.
        """
        try:
            ema20  = df['close'].ewm(span=20).mean().iloc[-1]
            ema50  = df['close'].ewm(span=50).mean().iloc[-1]
            ema200 = df['close'].ewm(span=200).mean().iloc[-1]
            if ema20 > ema50 > ema200: return 1
            if ema20 < ema50 < ema200: return -1
            return 0
        except Exception:
            return 0

    def _atr_percentile(self, symbol: str, current_atr: float) -> float:
        """
        Computes where current ATR sits in the historical distribution.
        Uses rolling window stored in self._atr_history.
        """
        history = self._atr_history.setdefault(symbol, [])
        history.append(current_atr)
        if len(history) > 1000:
            history.pop(0)

        if len(history) < 10:
            return 50.0  # Not enough data, assume median

        arr = np.array(history)
        return float(np.sum(arr <= current_atr) / len(arr) * 100)

    # ──────────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────────

    def classify(self, symbol: str, df_htf: pd.DataFrame, df_ltf: Optional[pd.DataFrame] = None) -> RegimeResult:
        """
        Classify the current market regime.

        Args:
            symbol:  Trading symbol (for ATR history tracking)
            df_htf:  Higher timeframe OHLCV (1h recommended) — regime source
            df_ltf:  Lower timeframe OHLCV (5m, optional) — for current ATR

        Returns:
            RegimeResult with allowed flag and sizing multiplier
        """
        df = df_htf
        if df is None or len(df) < 50:
            return RegimeResult(
                regime=Regime.UNKNOWN, allowed=True, confidence=0.0,
                reason="Insufficient data for regime classification — defaulting to ALLOW.",
                adx=0.0, hurst=0.5, atr_pct=0.0, atr_percentile=50.0, suggested_size_mult=0.75
            )

        # ── Indicators ──
        adx    = self._calculate_adx(df)
        hurst  = self._calculate_hurst(df['close'].values[-100:])
        ema_al = self._ema_alignment(df)

        atr_series = self._calculate_atr(df)
        current_atr = float(atr_series.iloc[-1]) if not atr_series.empty else 0.0
        price       = float(df['close'].iloc[-1])
        atr_pct     = (current_atr / price * 100) if price > 0 else 0.0
        atr_pctile  = self._atr_percentile(symbol, current_atr)

        # ── Classification Logic ──
        regime: Regime
        allowed = True
        confidence = 0.5
        size_mult = 1.0
        reason = ""

        # HIGH VOLATILITY: ATR in top 90th percentile
        if atr_pctile >= 90:
            regime     = Regime.HIGH_VOL
            allowed    = True   # Allow, but with reduced size
            size_mult  = 0.5
            confidence = 0.7
            reason     = (
                f"HIGH VOLATILITY REGIME: ATR at {atr_pctile:.0f}th percentile. "
                f"Signal allowed but position sized at 50% to accommodate expanded stops."
            )

        # TRENDING: ADX high + Hurst persistent + EMA aligned
        elif adx >= 25 and hurst >= 0.52:
            if ema_al == 1:
                regime = Regime.TRENDING_BULL
            elif ema_al == -1:
                regime = Regime.TRENDING_BEAR
            else:
                regime = Regime.TRENDING_BULL if adx > 30 else Regime.RANGING
            allowed    = True
            size_mult  = 1.0 if adx < 35 else 1.1  # Slightly larger in strong trend
            confidence = min(0.95, (adx - 25) / 25 + 0.5)
            reason     = (
                f"TRENDING REGIME: ADX={adx:.1f}, Hurst={hurst:.2f}, EMA={ema_al:+d}. "
                f"Full size. Order blocks have strong follow-through in this environment."
            )

        # RANGING / MEAN-REVERTING: Low ADX + low Hurst
        elif adx < 22 and hurst < 0.5:
            regime     = Regime.RANGING
            allowed    = True   # Ranging = ideal for sweeps (turtle soup)
            size_mult  = 0.85
            confidence = 0.65
            reason     = (
                f"RANGING REGIME: ADX={adx:.1f}, Hurst={hurst:.2f}. "
                f"Mean-reverting environment — prefer liquidity sweeps / turtle soups. "
                f"Breakout setups may fail. Size at 85%."
            )

        # CHOPPY: Low ADX + random Hurst (≈0.5) + no EMA alignment
        elif adx < 18 and 0.45 <= hurst <= 0.55 and ema_al == 0:
            regime     = Regime.CHOPPY
            allowed    = False
            size_mult  = 0.0
            confidence = 0.75
            reason     = (
                f"CHOPPY REGIME: ADX={adx:.1f}, Hurst={hurst:.2f}, EMA misaligned. "
                f"No directional edge. Signal BLOCKED. Wait for structure to clarify."
            )

        # BORDERLINE: Allow with reduced size
        else:
            regime     = Regime.RANGING
            allowed    = True
            size_mult  = 0.75
            confidence = 0.4
            reason     = (
                f"BORDERLINE REGIME: ADX={adx:.1f}, Hurst={hurst:.2f}. "
                f"Regime not well-defined. Proceeding with 75% size."
            )

        result = RegimeResult(
            regime=regime,
            allowed=allowed,
            confidence=confidence,
            reason=reason,
            adx=adx,
            hurst=hurst,
            atr_pct=atr_pct,
            atr_percentile=atr_pctile,
            suggested_size_mult=size_mult,
        )

        emoji = "✅" if allowed else "❌"
        logger.info(f"{emoji} [RegimeFilter] {symbol}: {result}")
        return result

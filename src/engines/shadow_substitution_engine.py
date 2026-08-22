"""
Shadow Substitution Engine
==========================
Experimental quantitative substitution modules for classical ICT concepts:
1. CVD (Cumulative Volume Delta) Absorption Divergence (Substitutes rigid FVG Retest)
2. Session VWAP +/- 2.0 Sigma Dispersion Bands (Substitutes static 50% Fib Equilibrium)
3. Open Interest / Liquidation Volume Flush Proxy (Substitutes subjective Judas detection)
4. 1D Kalman Filter State-Space Velocity Inflection (Substitutes lagging swing-break MSS)

Operates in 100% Shadow Mode: Computes metrics, evaluates signals, and logs outcomes
to track R:R expectancy before live graduation.
"""

import numpy as np
import pandas as pd
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

class KalmanStateFilter:
    """Zero-lag 1D State-Space Kalman Filter for instantaneous momentum inflection."""
    def __init__(self, process_variance=1e-4, measurement_variance=1e-2):
        self.q = process_variance
        self.r = measurement_variance
        self.posteri_estimate = 0.0
        self.posteri_error_estimate = 1.0

    def update(self, measurement: float) -> float:
        # Prediction
        priori_estimate = self.posteri_estimate
        priori_error_estimate = self.posteri_error_estimate + self.q

        # Measurement Update (Correction)
        blending_factor = priori_error_estimate / (priori_error_estimate + self.r)
        self.posteri_estimate = priori_estimate + blending_factor * (measurement - priori_estimate)
        self.posteri_error_estimate = (1.0 - blending_factor) * priori_error_estimate
        return self.posteri_estimate

    def filter_series(self, series: pd.Series) -> pd.Series:
        filtered = []
        for val in series:
            filtered.append(self.update(val))
        return pd.Series(filtered, index=series.index)


class ShadowSubstitutionEngine:
    def __init__(self):
        self.kalman = KalmanStateFilter()

    # ──────────────────────────────────────────────────────────────────────────
    # 1. Cumulative Volume Delta (CVD) Absorption
    # ──────────────────────────────────────────────────────────────────────────
    @staticmethod
    def calculate_cvd_proxy(df: pd.DataFrame) -> pd.Series:
        """
        Calculates a high-precision bar-by-bar delta volume proxy:
        Delta = Volume * ((Close - Low) - (High - Close)) / (High - Low)
        """
        candle_range = (df['high'] - df['low']).replace(0, 1e-6)
        buy_pressure = (df['close'] - df['low'])
        sell_pressure = (df['high'] - df['close'])
        bar_delta = df['volume'] * ((buy_pressure - sell_pressure) / candle_range)
        cvd = bar_delta.cumsum()
        return cvd

    def evaluate_cvd_divergence(self, df: pd.DataFrame, direction: str) -> Tuple[bool, float, str]:
        """
        Checks for CVD Absorption Divergence:
        - SHORT: Price makes higher/equal high, but CVD prints lower high (heavy sell absorption).
        - LONG: Price makes lower/equal low, but CVD prints higher low (heavy buy absorption).
        """
        if len(df) < 10:
            return False, 0.0, "Insufficient data"

        cvd = self.calculate_cvd_proxy(df)
        
        # Look back over last 5 bars vs prior 10 bars
        curr_price = df['close'].iloc[-1]
        prior_price = df['close'].iloc[-5]
        curr_cvd = cvd.iloc[-1]
        prior_cvd = cvd.iloc[-5]

        if direction.upper() in ["SHORT", "SELL"]:
            # Price pushed up or stayed flat, but CVD was heavily dumped
            price_delta = curr_price - prior_price
            cvd_delta = curr_cvd - prior_cvd
            if price_delta >= 0 and cvd_delta < 0:
                strength = min(abs(cvd_delta) / (abs(curr_cvd) + 1e-6), 1.0)
                return True, float(strength), "CVD Bearish Absorption (Aggressive Limit Sell Iceberg)"
        else: # LONG
            price_delta = curr_price - prior_price
            cvd_delta = curr_cvd - prior_cvd
            if price_delta <= 0 and cvd_delta > 0:
                strength = min(abs(cvd_delta) / (abs(curr_cvd) + 1e-6), 1.0)
                return True, float(strength), "CVD Bullish Absorption (Aggressive Limit Buy Iceberg)"

        return False, 0.0, "No CVD Divergence"

    # ──────────────────────────────────────────────────────────────────────────
    # 2. Session VWAP +/- 2.0 Sigma Dispersion Bands
    # ──────────────────────────────────────────────────────────────────────────
    @staticmethod
    def calculate_session_vwap_bands(df: pd.DataFrame) -> Dict[str, float]:
        """
        Computes rolling Volume-Weighted Average Price (VWAP) and Standard Deviation Bands.
        Returns: { 'vwap': float, 'upper_2sigma': float, 'lower_2sigma': float, 'z_score': float }
        """
        if len(df) < 10:
            return {}

        pv = (df['close'] * df['volume']).cumsum()
        vol = df['volume'].cumsum().replace(0, 1e-6)
        vwap = pv / vol

        # Standard Deviation of Price from VWAP
        variance = (((df['close'] - vwap) ** 2) * df['volume']).cumsum() / vol
        std_dev = np.sqrt(variance.replace(0, 1e-6))

        curr_close = df['close'].iloc[-1]
        curr_vwap = vwap.iloc[-1]
        curr_std = std_dev.iloc[-1]

        z_score = (curr_close - curr_vwap) / (curr_std + 1e-6)

        return {
            "vwap": float(curr_vwap),
            "upper_2sigma": float(curr_vwap + 2.0 * curr_std),
            "lower_2sigma": float(curr_vwap - 2.0 * curr_std),
            "z_score": float(z_score),
            "is_extreme_premium": bool(z_score >= 1.8),
            "is_extreme_discount": bool(z_score <= -1.8)
        }

    # ──────────────────────────────────────────────────────────────────────────
    # 3. Liquidation Volume Flush Proxy
    # ──────────────────────────────────────────────────────────────────────────
    @staticmethod
    def evaluate_liquidation_flush(df: pd.DataFrame) -> Tuple[bool, float, str]:
        """
        Detects stop-run liquidation flushes:
        Volume Spike > 2.5x of 20-bar average accompanied by a long wick (>=35% of bar).
        """
        if len(df) < 20:
            return False, 0.0, "Insufficient bars"

        curr_bar = df.iloc[-1]
        avg_vol = df['volume'].iloc[-20:-1].mean() + 1e-6
        vol_ratio = curr_bar['volume'] / avg_vol

        bar_range = curr_bar['high'] - curr_bar['low']
        if bar_range <= 0:
            return False, 0.0, "Zero range bar"

        upper_wick = curr_bar['high'] - max(curr_bar['open'], curr_bar['close'])
        lower_wick = min(curr_bar['open'], curr_bar['close']) - curr_bar['low']

        upper_wick_ratio = upper_wick / bar_range
        lower_wick_ratio = lower_wick / bar_range

        if vol_ratio >= 2.0 and upper_wick_ratio >= 0.35:
            return True, float(vol_ratio), "Top Liquidation Flush (Buy-Stop Cascade Swept)"
        elif vol_ratio >= 2.0 and lower_wick_ratio >= 0.35:
            return True, float(vol_ratio), "Bottom Liquidation Flush (Sell-Stop Cascade Swept)"

        return False, float(vol_ratio), "Normal Volume Profile"

    # ──────────────────────────────────────────────────────────────────────────
    # 4. Kalman State-Space Velocity Inflection (Zero-Lag MSS)
    # ──────────────────────────────────────────────────────────────────────────
    def evaluate_kalman_mss(self, df: pd.DataFrame) -> Tuple[str, float]:
        """
        Applies a Kalman filter to prices to measure instant slope inflection:
        Returns: ('BULLISH_SHIFT' | 'BEARISH_SHIFT' | 'NEUTRAL', slope_magnitude)
        """
        if len(df) < 15:
            return "NEUTRAL", 0.0

        filtered = self.kalman.filter_series(df['close'])
        
        # Calculate instantaneous slope
        slope_curr = filtered.iloc[-1] - filtered.iloc[-2]
        slope_prev = filtered.iloc[-2] - filtered.iloc[-3]

        # Shift from negative to positive = Bullish Shift
        if slope_prev < 0 and slope_curr > 0:
            return "BULLISH_SHIFT", float(abs(slope_curr))
        # Shift from positive to negative = Bearish Shift
        elif slope_prev > 0 and slope_curr < 0:
            return "BEARISH_SHIFT", float(abs(slope_curr))

        return "NEUTRAL", float(slope_curr)

    # ──────────────────────────────────────────────────────────────────────────
    # Full Shadow Evaluation Pipeline
    # ──────────────────────────────────────────────────────────────────────────
    def run_shadow_audit(self, symbol: str, df_5m: pd.DataFrame, candidate_direction: str = "SHORT") -> Dict[str, Any]:
        """
        Evaluates all 4 shadow substitution indicators on the latest market data.
        """
        cvd_active, cvd_str, cvd_msg = self.evaluate_cvd_divergence(df_5m, candidate_direction)
        vwap_data = self.calculate_session_vwap_bands(df_5m)
        liq_active, liq_ratio, liq_msg = self.evaluate_liquidation_flush(df_5m)
        kalman_shift, kalman_slope = self.evaluate_kalman_mss(df_5m)

        # Composite Shadow Confluence Score (0 to 10)
        shadow_score = 5.0
        if cvd_active: shadow_score += 1.5
        if vwap_data.get('is_extreme_premium') and candidate_direction == "SHORT": shadow_score += 1.5
        if vwap_data.get('is_extreme_discount') and candidate_direction == "LONG": shadow_score += 1.5
        if liq_active: shadow_score += 1.0
        if (kalman_shift == "BEARISH_SHIFT" and candidate_direction == "SHORT") or (kalman_shift == "BULLISH_SHIFT" and candidate_direction == "LONG"):
            shadow_score += 1.0

        shadow_score = min(shadow_score, 10.0)

        report = {
            "symbol": symbol,
            "direction": candidate_direction,
            "shadow_score": round(shadow_score, 2),
            "cvd_absorption": {
                "active": cvd_active,
                "strength": cvd_str,
                "details": cvd_msg
            },
            "session_vwap": vwap_data,
            "liquidation_flush": {
                "active": liq_active,
                "volume_ratio": round(liq_ratio, 2),
                "details": liq_msg
            },
            "kalman_mss": {
                "state": kalman_shift,
                "instantaneous_slope": round(kalman_slope, 4)
            }
        }
        return report

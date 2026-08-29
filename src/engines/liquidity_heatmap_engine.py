"""
Liquidity Heatmap & Stop Density Engine (Sovereign ICT Core)
============================================================
The primary governing law of price delivery in institutional SMC/ICT:
Price moves exclusively to:
  1. Purge resting liquidity pools (Stop Clusters / BSL / SSL)
  2. Rebalance market inefficiencies (Fair Value Gaps / Imbalances)

This engine calculates a live, continuous Liquidity Heatmap:
  - Scans and ranks all resting Buy-Side Liquidity (BSL) and Sell-Side Liquidity (SSL) pools.
  - Identifies Multi-Touch Equal Highs/Lows (EQH/EQL), Session Extremes (Asian, London, PDH/PDL).
  - Assigns a Density Weight (0-10) to each liquidity pocket.
  - Identifies the Primary Entry Sweep Magnet and the Opposing Destination Magnet (TP).
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timezone
import logging

logger = logging.getLogger("LiquidityHeatmapEngine")


class LiquidityHeatmapEngine:
    """
    Constructs an institutional liquidity density heatmap for a given asset.
    Identifies stop clusters and sets dynamic magnet targets.
    """

    def __init__(self, tolerance_pct: float = 0.0015):
        """
        :param tolerance_pct: Tolerance band (0.15%) to cluster nearby levels into a single dense pool.
        """
        self.tolerance_pct = tolerance_pct

    def extract_session_extremes(self, df_5m: pd.DataFrame) -> Dict[str, float]:
        """
        Extracts previous day high/low, Asian range, and London range from 5m dataframe.
        """
        extremes = {}
        if len(df_5m) < 48:
            return extremes

        try:
            # Assumes 'timestamp' or DatetimeIndex
            df = df_5m.copy()
            if 'timestamp' in df.columns:
                df['dt'] = pd.to_datetime(df['timestamp'], utc=True)
            elif isinstance(df.index, pd.DatetimeIndex):
                df['dt'] = df.index
            else:
                df['dt'] = pd.date_range(end=datetime.now(timezone.utc), periods=len(df), freq='5min')

            # Previous Day High / Low (past 24h to 48h window)
            last_24h = df.iloc[-288:-24] if len(df) >= 288 else df.iloc[:-12]
            if len(last_24h) > 0:
                extremes['PDH'] = float(last_24h['high'].max())
                extremes['PDL'] = float(last_24h['low'].min())

            # Asian Session (00:00 - 06:00 UTC)
            asian_bars = df[df['dt'].dt.hour.isin([0, 1, 2, 3, 4, 5])]
            if len(asian_bars) >= 6:
                extremes['ASIA_HIGH'] = float(asian_bars['high'].max())
                extremes['ASIA_LOW'] = float(asian_bars['low'].min())

            # London Open Range (07:00 - 10:00 UTC)
            london_bars = df[df['dt'].dt.hour.isin([7, 8, 9])]
            if len(london_bars) >= 6:
                extremes['LONDON_HIGH'] = float(london_bars['high'].max())
                extremes['LONDON_LOW'] = float(london_bars['low'].min())

        except Exception as e:
            logger.debug(f"Error extracting session extremes: {e}")

        return extremes

    def find_equal_extremes(self, df_5m: pd.DataFrame, window: int = 3, threshold_pct: float = 0.0010) -> List[Dict[str, Any]]:
        """
        Finds Equal Highs (EQH) and Equal Lows (EQL) with multiple touches (engineered liquidity).
        """
        clusters = []
        if len(df_5m) < 30:
            return clusters

        highs = df_5m['high'].values
        lows = df_5m['low'].values
        n = len(df_5m)

        # Detect swing highs & lows
        swing_high_prices = []
        swing_low_prices = []

        for i in range(window, n - window):
            if all(highs[i] >= highs[i - k] for k in range(1, window + 1)) and all(highs[i] >= highs[i + k] for k in range(1, window + 1)):
                swing_high_prices.append(highs[i])
            if all(lows[i] <= lows[i - k] for k in range(1, window + 1)) and all(lows[i] <= lows[i + k] for k in range(1, window + 1)):
                swing_low_prices.append(lows[i])

        # Cluster Swing Highs (Buy-Side Liquidity Pools)
        if len(swing_high_prices) >= 2:
            swing_high_prices.sort()
            current_cluster = [swing_high_prices[0]]
            for p in swing_high_prices[1:]:
                if abs(p - np.mean(current_cluster)) / np.mean(current_cluster) <= threshold_pct:
                    current_cluster.append(p)
                else:
                    if len(current_cluster) >= 2:
                        clusters.append({
                            "type": "BSL",
                            "label": f"EQUAL_HIGHS_{len(current_cluster)}x",
                            "price": float(np.mean(current_cluster)),
                            "touches": len(current_cluster),
                            "density_score": min(len(current_cluster) * 2.5, 9.0)
                        })
                    current_cluster = [p]
            if len(current_cluster) >= 2:
                clusters.append({
                    "type": "BSL",
                    "label": f"EQUAL_HIGHS_{len(current_cluster)}x",
                    "price": float(np.mean(current_cluster)),
                    "touches": len(current_cluster),
                    "density_score": min(len(current_cluster) * 2.5, 9.0)
                })

        # Cluster Swing Lows (Sell-Side Liquidity Pools)
        if len(swing_low_prices) >= 2:
            swing_low_prices.sort()
            current_cluster = [swing_low_prices[0]]
            for p in swing_low_prices[1:]:
                if abs(p - np.mean(current_cluster)) / np.mean(current_cluster) <= threshold_pct:
                    current_cluster.append(p)
                else:
                    if len(current_cluster) >= 2:
                        clusters.append({
                            "type": "SSL",
                            "label": f"EQUAL_LOWS_{len(current_cluster)}x",
                            "price": float(np.mean(current_cluster)),
                            "touches": len(current_cluster),
                            "density_score": min(len(current_cluster) * 2.5, 9.0)
                        })
                    current_cluster = [p]
            if len(current_cluster) >= 2:
                clusters.append({
                    "type": "SSL",
                    "label": f"EQUAL_LOWS_{len(current_cluster)}x",
                    "price": float(np.mean(current_cluster)),
                    "touches": len(current_cluster),
                    "density_score": min(len(current_cluster) * 2.5, 9.0)
                })

        return clusters

    def build_liquidity_map(self, df_5m: pd.DataFrame, df_1h: pd.DataFrame) -> Dict[str, Any]:
        """
        Builds the unified Liquidity Heatmap containing:
          - BSL Pools (Buy-Side Liquidity above current price)
          - SSL Pools (Sell-Side Liquidity below current price)
          - Density Score and Primary Destination Magnets
        """
        current_price = float(df_5m['close'].iloc[-1])
        extremes = self.extract_session_extremes(df_5m)
        eq_clusters = self.find_equal_extremes(df_5m)

        pools: List[Dict[str, Any]] = []

        # 1. Add Session Extremes
        for label, price in extremes.items():
            pool_type = "BSL" if price > current_price else "SSL"
            density = 8.0 if "PD" in label else (7.0 if "LONDON" in label else 6.0)
            pools.append({
                "type": pool_type,
                "label": label,
                "price": price,
                "touches": 1,
                "density_score": density,
                "distance_pct": abs(price - current_price) / current_price
            })

        # 2. Add Equal Highs / Lows Clusters
        for c in eq_clusters:
            dist = abs(c['price'] - current_price) / current_price
            c['distance_pct'] = dist
            pools.append(c)

        # 3. Add HTF 1H Swing Points
        if len(df_1h) >= 20:
            h_1h = df_1h['high'].values
            l_1h = df_1h['low'].values
            for i in range(2, len(df_1h) - 2):
                if h_1h[i] == max(h_1h[i-2:i+3]):
                    p = float(h_1h[i])
                    if p > current_price:
                        pools.append({"type": "BSL", "label": "1H_SWING_HIGH", "price": p, "touches": 1, "density_score": 6.5, "distance_pct": (p - current_price) / current_price})
                if l_1h[i] == min(l_1h[i-2:i+3]):
                    p = float(l_1h[i])
                    if p < current_price:
                        pools.append({"type": "SSL", "label": "1H_SWING_LOW", "price": p, "touches": 1, "density_score": 6.5, "distance_pct": (current_price - p) / current_price})

        # Merge Confluent Pools (Within tolerance_pct)
        bsl_pools = [p for p in pools if p['type'] == 'BSL']
        ssl_pools = [p for p in pools if p['type'] == 'SSL']

        merged_bsl = self._merge_confluent_pools(bsl_pools, is_above=True)
        merged_ssl = self._merge_confluent_pools(ssl_pools, is_above=False)

        # Primary Magnets (Closest High-Density Pool)
        primary_bsl_magnet = merged_bsl[0] if merged_bsl else None
        primary_ssl_magnet = merged_ssl[0] if merged_ssl else None

        return {
            "current_price": current_price,
            "bsl_pools": merged_bsl,
            "ssl_pools": merged_ssl,
            "primary_bsl_magnet": primary_bsl_magnet,
            "primary_ssl_magnet": primary_ssl_magnet,
            "total_pools_tracked": len(merged_bsl) + len(merged_ssl)
        }

    def _merge_confluent_pools(self, pool_list: List[Dict[str, Any]], is_above: bool) -> List[Dict[str, Any]]:
        """Groups nearby levels within tolerance into super-dense liquidity zones."""
        if not pool_list:
            return []

        # Sort by distance from market price (ascending)
        pool_list.sort(key=lambda x: x['distance_pct'])

        merged = []
        for p in pool_list:
            matched = False
            for m in merged:
                if abs(p['price'] - m['price']) / m['price'] <= self.tolerance_pct:
                    # Confluence found! Stack density scores
                    m['density_score'] = min(m['density_score'] + (p['density_score'] * 0.4), 10.0)
                    m['labels'].append(p['label'])
                    m['touches'] += p.get('touches', 1)
                    matched = True
                    break
            if not matched:
                merged.append({
                    "type": p['type'],
                    "price": p['price'],
                    "density_score": p['density_score'],
                    "labels": [p['label']],
                    "touches": p.get('touches', 1),
                    "distance_pct": p['distance_pct']
                })

        # Sort by density and proximity
        merged.sort(key=lambda x: (-x['density_score'], x['distance_pct']))
        return merged

    def audit_sweep_against_heatmap(
        self,
        sweep_price: float,
        direction: str,
        df_5m: pd.DataFrame,
        df_1h: pd.DataFrame
    ) -> Tuple[bool, float, str, Optional[float]]:
        """
        Audits a proposed entry sweep against the live Liquidity Heatmap:
          1. Did the sweep hit a verified high-density stop cluster?
          2. Where is the opposing destination magnet for Take Profit?

        Returns: (is_high_density_sweep, density_score, audit_details, dynamic_tp_target)
        """
        l_map = self.build_liquidity_map(df_5m, df_1h)

        if direction.upper() in ["LONG", "BUY"]:
            # Long trades sweep Sell-Side Liquidity (SSL) and target Buy-Side Liquidity (BSL)
            target_pools = l_map['ssl_pools']
            opposing_magnet = l_map['primary_bsl_magnet']
        else:
            # Short trades sweep Buy-Side Liquidity (BSL) and target Sell-Side Liquidity (SSL)
            target_pools = l_map['bsl_pools']
            opposing_magnet = l_map['primary_ssl_magnet']

        # Find if the sweep price aligns with a known dense pool
        matched_pool = None
        for pool in target_pools:
            if abs(sweep_price - pool['price']) / pool['price'] <= self.tolerance_pct * 1.5:
                matched_pool = pool
                break

        density_score = matched_pool['density_score'] if matched_pool else 4.0
        is_verified = density_score >= 6.0
        labels_str = ", ".join(matched_pool['labels']) if matched_pool else "Discretionary Local Swing"

        dynamic_tp = opposing_magnet['price'] if opposing_magnet else None
        opposing_labels = ", ".join(opposing_magnet['labels']) if opposing_magnet else "N/A"

        audit_msg = (
            f"Liquidity Density: {density_score:.1f}/10 [{labels_str}] | "
            f"Opposing Target Magnet: ${dynamic_tp:.2f} [{opposing_labels}]" if dynamic_tp
            else f"Liquidity Density: {density_score:.1f}/10 [{labels_str}] | Target: ATR Multiple"
        )

        return is_verified, density_score, audit_msg, dynamic_tp

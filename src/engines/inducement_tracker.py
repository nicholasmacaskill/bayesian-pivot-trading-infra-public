import os
import json
import sqlite3
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from src.core.config import Config

logger = logging.getLogger(__name__)

class InducementTracker:
    """
    Detects, logs, and forensically analyzes extreme price outliers / Judas swings.
    Captures pre-spike conditions and measures post-spike reversal vs expansion dynamics.
    """
    def __init__(self, db_path: str = None):
        self.db_path = db_path or Config.DB_PATH
        self._init_db()

    def _init_db(self):
        """Initializes the inducement_events table in SQLite."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS inducement_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    symbol TEXT,
                    candle_type TEXT,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    range_size REAL,
                    range_atr_mult REAL,
                    upper_wick_pct REAL,
                    lower_wick_pct REAL,
                    vol_mult REAL,
                    utc_hour INTEGER,
                    utc_minute INTEGER,
                    session_tag TEXT,
                    prior_compression_ratio REAL,
                    smt_strength REAL,
                    swept_level_type TEXT,
                    status TEXT DEFAULT 'PENDING',
                    resolution TEXT DEFAULT 'PENDING',
                    reversal_r REAL DEFAULT 0.0,
                    bars_to_reversal INTEGER DEFAULT 0,
                    resolved_at TEXT,
                    notes TEXT
                );
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"[InducementTracker] DB Init Error: {e}")

    def detect_outlier_candle(self, df: pd.DataFrame, idx: int = -1) -> Optional[Dict[str, Any]]:
        """
        Evaluates a single candle for extreme outlier / inducement characteristics.
        Criteria:
          1. Range >= 2.0x rolling 20-period ATR
          2. Upper or Lower Wick Ratio >= 60% of total candle range (Liquidity grab wick)
          3. Volume Spike >= 1.8x rolling 20-period average volume
        """
        if len(df) < 30:
            return None

        # Resolve index
        pos = len(df) + idx if idx < 0 else idx
        if pos < 25 or pos >= len(df):
            return None

        row = df.iloc[pos]
        prior_df = df.iloc[pos-20:pos]

        o = float(row['open'])
        h = float(row['high'])
        l = float(row['low'])
        c = float(row['close'])
        v = float(row.get('volume', 0.0))

        candle_range = h - l
        if candle_range <= 0:
            return None

        # 1. Rolling ATR
        prior_ranges = prior_df['high'] - prior_df['low']
        avg_range = float(prior_ranges.mean()) if len(prior_ranges) > 0 else candle_range
        range_mult = candle_range / avg_range if avg_range > 0 else 1.0

        # 2. Wick Ratios
        body_top = max(o, c)
        body_bottom = min(o, c)
        upper_wick = h - body_top
        lower_wick = body_bottom - l
        upper_wick_pct = (upper_wick / candle_range) * 100.0
        lower_wick_pct = (lower_wick / candle_range) * 100.0

        # 3. Volume Multiplier
        avg_vol = float(prior_df['volume'].mean()) if 'volume' in prior_df.columns and len(prior_df) > 0 else 1.0
        vol_mult = (v / avg_vol) if avg_vol > 0 else 1.0

        # Outlier Detection Rules
        is_bull_inducement = (upper_wick_pct >= 60.0) and (range_mult >= 1.8 or vol_mult >= 2.0)
        is_bear_inducement = (lower_wick_pct >= 60.0) and (range_mult >= 1.8 or vol_mult >= 2.0)

        if not (is_bull_inducement or is_bear_inducement):
            return None

        candle_type = "BEARISH_INDUCEMENT_WICK" if is_bull_inducement else "BULLISH_INDUCEMENT_WICK"

        # 4. Pre-Inducement Squeeze / Compression Ratio
        # (Compare 5-bar ATR to 20-bar ATR prior to spike)
        recent_atr = float((df.iloc[pos-5:pos]['high'] - df.iloc[pos-5:pos]['low']).mean())
        compression_ratio = recent_atr / avg_range if avg_range > 0 else 1.0

        # 5. Session Phase
        ts = row.get('timestamp')
        if isinstance(ts, str):
            dt = pd.to_datetime(ts)
        elif isinstance(ts, (pd.Timestamp, datetime)):
            dt = ts
        else:
            dt = datetime.now(timezone.utc)

        utc_hour = dt.hour
        utc_minute = dt.minute

        if 6 <= utc_hour <= 10:
            session_tag = "LONDON_KILLZONE"
        elif 12 <= utc_hour <= 16:
            session_tag = "NY_KILLZONE"
        elif 0 <= utc_hour <= 4:
            session_tag = "ASIAN_RANGE"
        else:
            session_tag = "OFF_HOURS"

        return {
            'timestamp': str(ts),
            'symbol': str(row.get('symbol', 'BTC/USD')),
            'candle_type': candle_type,
            'open': o,
            'high': h,
            'low': l,
            'close': c,
            'range_size': candle_range,
            'range_atr_mult': round(range_mult, 2),
            'upper_wick_pct': round(upper_wick_pct, 1),
            'lower_wick_pct': round(lower_wick_pct, 1),
            'vol_mult': round(vol_mult, 2),
            'utc_hour': utc_hour,
            'utc_minute': utc_minute,
            'session_tag': session_tag,
            'prior_compression_ratio': round(compression_ratio, 2),
            'smt_strength': float(row.get('smt_strength', 0.0)) if not pd.isna(row.get('smt_strength', 0.0)) else 0.0,
            'swept_level_type': "EQUAL_HIGHS" if is_bull_inducement else "EQUAL_LOWS",
            'status': 'PENDING'
        }

    def log_inducement_event(self, event_data: Dict[str, Any]) -> int:
        """Persists a detected inducement event to SQLite."""
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO inducement_events (
                    timestamp, symbol, candle_type, open, high, low, close,
                    range_size, range_atr_mult, upper_wick_pct, lower_wick_pct, vol_mult,
                    utc_hour, utc_minute, session_tag, prior_compression_ratio,
                    smt_strength, swept_level_type, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
            """, (
                event_data['timestamp'], event_data['symbol'], event_data['candle_type'],
                event_data['open'], event_data['high'], event_data['low'], event_data['close'],
                event_data['range_size'], event_data['range_atr_mult'], event_data['upper_wick_pct'],
                event_data['lower_wick_pct'], event_data['vol_mult'], event_data['utc_hour'],
                event_data['utc_minute'], event_data['session_tag'], event_data['prior_compression_ratio'],
                event_data['smt_strength'], event_data['swept_level_type']
            ))
            event_id = cur.lastrowid
            conn.commit()
            conn.close()
            logger.info(f"🚨 [InducementTracker] Logged Outlier Event #{event_id}: {event_data['symbol']} {event_data['candle_type']} ({event_data['range_atr_mult']}x ATR)")
            return event_id
        except Exception as e:
            logger.error(f"[InducementTracker] Logging Error: {e}")
            return -1

    def resolve_inducements_with_future_data(self, df: pd.DataFrame, event_id: int, spike_idx: int, lookahead_bars: int = 12) -> Dict[str, Any]:
        """
        Evaluates future candles to determine if the outlier was a:
          - TRUE_INDUCEMENT: Price reversed >= 1.5x spike range in opposite direction.
          - BREAKOUT_EXPANSION: Price continued in the direction of the spike.
          - CHOPPY_CONSOLIDATION: Price stalled inside the spike range.
        """
        if spike_idx + lookahead_bars > len(df):
            return {'status': 'PENDING'}

        spike_row = df.iloc[spike_idx]
        future_df = df.iloc[spike_idx+1:spike_idx+1+lookahead_bars]

        spike_high = float(spike_row['high'])
        spike_low = float(spike_row['low'])
        spike_range = spike_high - spike_low
        is_bear_inducement_wick = (spike_high - max(spike_row['open'], spike_row['close'])) > (min(spike_row['open'], spike_row['close']) - spike_low)

        if is_bear_inducement_wick:
            # We spiked upward (swept highs). Reversal = price drops below spike_low.
            lowest_future = float(future_df['low'].min())
            highest_future = float(future_df['high'].max())
            drop_dist = spike_high - lowest_future
            reversal_r = drop_dist / spike_range if spike_range > 0 else 0.0

            if lowest_future < (spike_low - (spike_range * 0.5)):
                resolution = "TRUE_INDUCEMENT_REVERSAL"
            elif highest_future > (spike_high + (spike_range * 0.5)):
                resolution = "BREAKOUT_EXPANSION"
            else:
                resolution = "CONSOLIDATION_STALL"
        else:
            # We spiked downward (swept lows). Reversal = price rallies above spike_high.
            lowest_future = float(future_df['low'].min())
            highest_future = float(future_df['high'].max())
            rally_dist = highest_future - spike_low
            reversal_r = rally_dist / spike_range if spike_range > 0 else 0.0

            if highest_future > (spike_high + (spike_range * 0.5)):
                resolution = "TRUE_INDUCEMENT_REVERSAL"
            elif lowest_future < (spike_low - (spike_range * 0.5)):
                resolution = "BREAKOUT_EXPANSION"
            else:
                resolution = "CONSOLIDATION_STALL"

        res_dict = {
            'event_id': event_id,
            'status': 'RESOLVED',
            'resolution': resolution,
            'reversal_r': round(reversal_r, 2),
            'resolved_at': str(future_df.iloc[-1]['timestamp'])
        }

        # Update DB if event_id is valid
        if event_id > 0:
            try:
                conn = sqlite3.connect(self.db_path)
                conn.execute("""
                    UPDATE inducement_events
                    SET status = 'RESOLVED', resolution = ?, reversal_r = ?, resolved_at = ?
                    WHERE id = ?
                """, (res_dict['resolution'], res_dict['reversal_r'], res_dict['resolved_at'], event_id))
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"[InducementTracker] DB Update Error: {e}")

        return res_dict

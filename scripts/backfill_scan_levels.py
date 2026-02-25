"""
Backfill Scan Levels + Resolve Outcomes
=========================================
Retroactively adds entry/stop_loss/target to all existing scans that
are missing trade levels, then resolves their outcomes (WIN/LOSS).

This unlocks ALL historical scans as training data immediately.

Logic:
    1. Fetch scans with no entry price
    2. For each: fetch 5m candles at scan timestamp
    3. Entry = close price at that candle
    4. ATR(14) at that moment → stop = entry ± 2×ATR
    5. Target = 3R in trade direction
    6. Write levels back to Supabase
    7. Run outcome resolver on those newly-enriched records

Run: python3 scripts/backfill_scan_levels.py
     python3 scripts/backfill_scan_levels.py --limit 100   (batch)
     python3 scripts/backfill_scan_levels.py --dry-run      (preview only)
"""
import os
import sys
import time
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

sys.path.append(os.getcwd())

from src.core.supabase_client import supabase
from src.engines.smc_scanner import SMCScanner

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger("BackfillLevels")

scanner = SMCScanner()
DRY_RUN = "--dry-run" in sys.argv

# ── Helpers ────────────────────────────────────────────────────────────────────

def parse_scan_timestamp(ts_str):
    """Safely parses ISO timestamp string to naive UTC datetime."""
    try:
        ts = ts_str.replace('Z', '').split('+')[0]
        if 'T' in ts:
            dp, tp = ts.split('T')
            tp = tp.split('.')[0]  # Drop microseconds
            ts = f"{dp}T{tp}"
        return datetime.fromisoformat(ts)
    except Exception as e:
        logger.warning(f"Timestamp parse error: {e} | {ts_str}")
        return None

def infer_direction(scan):
    """Determines trade direction from scan bias or pattern."""
    bias = scan.get('bias', '').lower()
    pattern = scan.get('pattern', '').lower()
    if 'bear' in bias or 'sell' in bias or 'short' in bias:
        return 'SELL'
    if 'bull' in bias or 'buy' in bias or 'long' in bias:
        return 'BUY'
    if 'bear' in pattern or 'short' in pattern:
        return 'SELL'
    if 'bull' in pattern or 'long' in pattern:
        return 'BUY'
    return 'SELL'  # Default: most scans are bearish setups

def calculate_atr(df, period=14):
    """Calculates ATR(14) from OHLCV dataframe."""
    high_low   = df['high'] - df['low']
    high_close = (df['high'] - df['close'].shift()).abs()
    low_close  = (df['low']  - df['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean().iloc[-1]

def fetch_candles_at(symbol, entry_dt, limit=200):
    """Fetches 5m candles starting ~2h before entry_dt."""
    try:
        since_ms = int((entry_dt - timedelta(hours=2)).timestamp() * 1000)
        norm = symbol.replace('USD', 'USDT') if 'USDT' not in symbol else symbol
        ohlcv = scanner.exchange.fetch_ohlcv(norm, '5m', since=since_ms, limit=limit)
        if not ohlcv:
            return None
        df = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        logger.warning(f"Candle fetch error ({symbol}): {e}")
        return None

def infer_levels(scan):
    """
    Core inference: fetches candles at scan time, calculates entry/SL/target.
    Returns dict: {entry, stop_loss, target, r_multiple} or None if data unavailable.
    """
    ts_str = scan.get('timestamp', '')
    entry_dt = parse_scan_timestamp(ts_str)
    if not entry_dt:
        return None

    symbol   = scan.get('symbol', 'BTC/USDT')
    direction = infer_direction(scan)

    df = fetch_candles_at(symbol, entry_dt)
    if df is None or len(df) < 15:
        return None

    # Find the candle closest to the scan timestamp
    df['ts_diff'] = (df['timestamp'] - entry_dt).abs()
    entry_candle = df.loc[df['ts_diff'].idxmin()]
    entry_price  = float(entry_candle['close'])

    if entry_price <= 0:
        return None

    # ATR for stop sizing
    atr = calculate_atr(df)
    if pd.isna(atr) or atr <= 0:
        # Fallback: 0.5% of price
        atr = entry_price * 0.005

    stop_distance = atr * 2.0
    r_multiple    = 3.0

    if direction == 'SELL':
        stop_loss = entry_price + stop_distance
        target    = entry_price - (stop_distance * r_multiple)
    else:
        stop_loss = entry_price - stop_distance
        target    = entry_price + (stop_distance * r_multiple)

    return {
        'entry':      round(entry_price, 4),
        'stop_loss':  round(stop_loss, 4),
        'target':     round(target, 4),
        'r_multiple': r_multiple,
        'outcome':    'OPEN',
    }

def resolve_outcome(entry, stop_loss, target, direction, candles_after):
    """Walks forward through candles to find if TP or SL was hit first."""
    if not candles_after:
        return 'OPEN', None

    risk = abs(entry - stop_loss)
    if risk == 0:
        return 'OPEN', None

    is_short = direction == 'SELL'

    for row in candles_after:
        _, _, high, low, _, _ = row
        if is_short:
            if low  <= target:    return 'WIN',  round(abs(entry - target) / risk, 2)
            if high >= stop_loss: return 'LOSS', round(-1.0, 2)
        else:
            if high >= target:    return 'WIN',  round(abs(target - entry) / risk, 2)
            if low  <= stop_loss: return 'LOSS', round(-1.0, 2)

    return 'OPEN', None

# ── Main ────────────────────────────────────────────────────────────────────────

def run(limit=500):
    if not supabase.client:
        logger.error("Supabase not connected.")
        return

    logger.info(f"🔍 Fetching scans with missing entry levels (limit={limit})...")

    # Fetch scans with no entry price set
    res = supabase.client.table('scans') \
        .select('*') \
        .is_('entry', 'null') \
        .not_.eq('pattern', 'Searching...') \
        .order('timestamp', desc=False) \
        .limit(limit) \
        .execute()

    scans = res.data or []
    logger.info(f"📦 {len(scans)} scans to backfill.")

    levelled  = 0
    resolved  = 0
    skipped   = 0
    wins      = 0
    losses    = 0

    for i, scan in enumerate(scans):
        try:
            symbol    = scan.get('symbol', 'BTC/USDT')
            scan_id   = scan.get('id')
            ts_str    = scan.get('timestamp', '')
            direction = infer_direction(scan)

            logger.info(f"[{i+1}/{len(scans)}] {symbol} {direction} @ {ts_str[:16]}")

            # ── Step 1: Infer levels ─────────────────────────────────────────
            levels = infer_levels(scan)
            if not levels:
                logger.debug(f"   ⚠️  Skipping — no candle data")
                skipped += 1
                continue

            logger.info(f"   Entry: {levels['entry']} | SL: {levels['stop_loss']} | TP: {levels['target']}")

            if not DRY_RUN:
                supabase.client.table('scans').update(levels).eq('id', scan_id).execute()
            levelled += 1

            # ── Step 2: Resolve outcome from forward candles ─────────────────
            entry_dt = parse_scan_timestamp(ts_str)
            if entry_dt and (datetime.utcnow() - entry_dt).total_seconds() > 3600:
                since_ms = int(entry_dt.timestamp() * 1000)
                norm = symbol.replace('USD', 'USDT') if 'USDT' not in symbol else symbol
                candles_after = scanner.exchange.fetch_ohlcv(norm, '5m', since=since_ms, limit=500)

                outcome, actual_r = resolve_outcome(
                    levels['entry'], levels['stop_loss'], levels['target'],
                    direction, candles_after
                )

                if outcome in ('WIN', 'LOSS'):
                    emoji = "✅" if outcome == 'WIN' else "❌"
                    logger.info(f"   {emoji} Outcome: {outcome} ({actual_r}R)")

                    if not DRY_RUN:
                        supabase.client.table('scans').update({
                            'outcome':     outcome,
                            'actual_r':    actual_r,
                            'resolved_at': datetime.utcnow().isoformat()
                        }).eq('id', scan_id).execute()

                    resolved += 1
                    if outcome == 'WIN':   wins   += 1
                    if outcome == 'LOSS':  losses += 1
                else:
                    logger.info(f"   ⏳ Outcome: still OPEN / unresolved")

            # Rate limiting — be kind to the exchange API
            time.sleep(0.3)

        except Exception as e:
            logger.error(f"Error processing scan {scan.get('id')}: {e}")
            continue

    # ── Summary ──────────────────────────────────────────────────────────────
    print()
    print("=" * 55)
    print("  BACKFILL COMPLETE")
    print("=" * 55)
    print(f"  Scans processed:  {len(scans)}")
    print(f"  Levels inferred:  {levelled}")
    print(f"  Outcomes resolved:{resolved}")
    print(f"    WIN:  {wins}")
    print(f"    LOSS: {losses}")
    print(f"  Skipped:          {skipped}")
    if resolved > 0:
        wr = wins / resolved * 100
        print(f"  Win Rate:         {wr:.1f}%")
    print()
    print(f"  Next: python3 scripts/export_training_data.py")
    print("=" * 55)

    if DRY_RUN:
        print("\n  ⚠️  DRY RUN — no changes written to Supabase.")

if __name__ == "__main__":
    limit = 500
    for arg in sys.argv[1:]:
        if arg.startswith('--limit='):
            limit = int(arg.split('=')[1])
        elif arg.isdigit():
            limit = int(arg)

    run(limit=limit)

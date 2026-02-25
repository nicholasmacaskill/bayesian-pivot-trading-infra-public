"""
Resolve Scan Outcomes
=====================
For every scan with entry/stop/target that hasn't been resolved yet,
fetch forward price data and determine: did price hit TP or SL first?

Writes back: outcome (WIN/LOSS), actual_r, resolved_at.

Run: python3 scripts/resolve_scan_outcomes.py
Run daily via cron: 0 8 * * * cd /path/to/project && python3 scripts/resolve_scan_outcomes.py
"""
import os
import sys
import logging
from datetime import datetime, timedelta

sys.path.append(os.getcwd())

from src.core.supabase_client import supabase
from src.engines.smc_scanner import SMCScanner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("OutcomeResolver")

scanner = SMCScanner()

def fetch_candles_after(symbol, since_timestamp, limit=500):
    """Fetches candles starting from a given timestamp."""
    try:
        since_ms = int(since_timestamp.timestamp() * 1000)
        ohlcv = scanner.exchange.fetch_ohlcv(
            symbol.replace('USD', 'USDT'),  # Normalize for Coinbase
            '5m',
            since=since_ms,
            limit=limit
        )
        return ohlcv
    except Exception as e:
        logger.error(f"Candle fetch error ({symbol}): {e}")
        return []

def resolve_outcome(entry, stop_loss, target, direction, candles):
    """
    Walks forward through candles to find if TP or SL was hit first.
    Returns: ('WIN' | 'LOSS' | 'OPEN', actual_r)
    """
    if not candles or not entry or not stop_loss or not target:
        return 'OPEN', None

    risk = abs(entry - stop_loss)
    if risk == 0:
        return 'OPEN', None

    is_short = direction in ('SHORT', 'SELL', 'Bearish') or target < entry

    for candle in candles:
        _, open_, high, low, close, _ = candle

        if is_short:
            # SHORT: TP is below entry, SL is above
            if low <= target:
                actual_r = abs(entry - target) / risk
                return 'WIN', round(actual_r, 2)
            if high >= stop_loss:
                actual_r = -abs(entry - stop_loss) / risk
                return 'LOSS', round(actual_r, 2)
        else:
            # LONG: TP is above entry, SL is below
            if high >= target:
                actual_r = abs(target - entry) / risk
                return 'WIN', round(actual_r, 2)
            if low <= stop_loss:
                actual_r = -abs(entry - stop_loss) / risk
                return 'LOSS', round(actual_r, 2)

    return 'OPEN', None  # Not yet resolved

def run_resolver(limit=200):
    if not supabase.client:
        logger.error("Supabase not connected.")
        return

    logger.info(f"🔍 Fetching up to {limit} unresolved scans...")

    # Fetch OPEN scans that have trade levels
    res = supabase.client.table('scans')\
        .select('*')\
        .eq('outcome', 'OPEN')\
        .not_.is_('entry', 'null')\
        .not_.is_('stop_loss', 'null')\
        .not_.is_('target', 'null')\
        .order('timestamp', desc=False)\
        .limit(limit)\
        .execute()

    scans = res.data or []
    logger.info(f"📦 Found {len(scans)} unresolved scans.")

    resolved = 0
    for scan in scans:
        try:
            ts_str = scan['timestamp'].replace('Z', '').split('+')[0]
            ts = datetime.fromisoformat(ts_str)

            # Skip scans less than 1 hour old (need time to play out)
            if (datetime.utcnow() - ts).total_seconds() < 3600:
                continue

            symbol = scan['symbol']
            entry = scan.get('entry')
            stop_loss = scan.get('stop_loss')
            target = scan.get('target')
            direction = scan.get('bias', 'Unknown')

            candles = fetch_candles_after(symbol, ts)
            outcome, actual_r = resolve_outcome(entry, stop_loss, target, direction, candles)

            if outcome == 'OPEN':
                # Still in play — skip for now unless it's old
                if (datetime.utcnow() - ts).total_seconds() > 86400 * 3:
                    outcome = 'EXPIRED'  # Too old to resolve = likely moved SL manually
            
            if outcome != 'OPEN':
                supabase.client.table('scans').update({
                    'outcome': outcome,
                    'actual_r': actual_r,
                    'resolved_at': datetime.utcnow().isoformat()
                }).eq('id', scan['id']).execute()

                emoji = "✅" if outcome == 'WIN' else "❌" if outcome == 'LOSS' else "⏰"
                logger.info(f"{emoji} [{symbol}] {scan['pattern']} → {outcome} ({actual_r}R)")
                resolved += 1

        except Exception as e:
            logger.error(f"Error resolving scan {scan.get('id')}: {e}")
            continue

    logger.info(f"🏁 Done. Resolved {resolved}/{len(scans)} scans.")

if __name__ == "__main__":
    import sys
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    run_resolver(limit=limit)

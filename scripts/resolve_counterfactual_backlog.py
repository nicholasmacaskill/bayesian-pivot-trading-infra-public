"""
scripts/resolve_counterfactual_backlog.py
=========================================
Historical Counterfactual Backfill & Resolution Engine.
Resolves open/pending shadow trades against real historical 5-minute candle data,
populating ground truth (HIT_TP, HIT_SL, EXPIRED) for AI RAG memory and tournament variants.
"""

import os
import sys
import logging
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional
import pandas as pd
import yfinance as yf

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.config import Config
from src.core.database import get_db_connection
from src.engines.champion_challenger_lab import ChampionChallengerLab
from src.engines.counterfactual_tracker import CounterfactualTracker

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger("CounterfactualBackfill")

SYMBOL_MAP = {
    "BTC/USD": "BTC-USD",
    "ETH/USD": "ETH-USD",
    "SOL/USD": "SOL-USD",
    "XAU/USD": "GC=F"
}


def load_historical_data(start_date: str) -> Dict[str, pd.DataFrame]:
    """Downloads and caches 5m candle data for all shadow assets."""
    candle_cache = {}
    logger.info(f"📥 Downloading historical 5m bars starting from {start_date}...")
    for sym, ticker in SYMBOL_MAP.items():
        try:
            df = yf.download(ticker, start=start_date, interval="5m", progress=False)
            if not df.empty:
                # Flatten multi-index columns if present
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = [c[0] for c in df.columns]
                # Ensure UTC index
                if df.index.tz is None:
                    df.index = df.index.tz_localize("UTC")
                else:
                    df.index = df.index.tz_convert("UTC")
                candle_cache[sym] = df
                logger.info(f"  ✔ {sym:7s} ({ticker}): {len(df)} 5m bars loaded.")
            else:
                logger.warning(f"  ⚠️ No data returned for {sym} ({ticker})")
        except Exception as e:
            logger.error(f"  ❌ Error downloading data for {sym}: {e}")
    return candle_cache


def resolve_trade_outcome(
    trade: Dict[str, Any],
    bars: pd.DataFrame,
    now_utc: datetime
) -> Optional[Dict[str, Any]]:
    """
    Evaluates a single trade forward in time from its entry timestamp.
    Returns resolution dict if resolved, or None if still active within 48h.
    """
    t_id = trade["id"]
    direction = str(trade.get("direction", "LONG")).upper()
    entry = float(trade.get("entry_price") or 0.0)
    sl = float(trade.get("stop_loss") or 0.0)
    tp = float(trade.get("take_profit_1") or 0.0)

    # Parse created_at timestamp
    raw_ts = str(trade.get("timestamp", ""))
    try:
        t_entry = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        if t_entry.tzinfo is None:
            t_entry = t_entry.replace(tzinfo=timezone.utc)
    except Exception:
        return None

    # Slice forward candles: [t_entry, t_entry + 48h]
    t_max = t_entry + timedelta(hours=48)
    forward_bars = bars[(bars.index >= t_entry) & (bars.index <= t_max)]

    is_long = direction in ["BUY", "LONG"]

    for b_time, bar in forward_bars.iterrows():
        high = float(bar["High"])
        low = float(bar["Low"])

        if is_long:
            # Check for Stop Loss hit
            sl_hit = sl > 0 and low <= sl
            # Check for Take Profit hit
            tp_hit = tp > 0 and high >= tp

            if sl_hit and tp_hit:
                # Intra-candle collision: pessimistic assumption is SL hit first
                return {
                    "outcome": "HIT_SL",
                    "simulated_r": -1.0,
                    "simulated_pnl": -100.0,
                    "closed_at": b_time.isoformat()
                }
            elif sl_hit:
                return {
                    "outcome": "HIT_SL",
                    "simulated_r": -1.0,
                    "simulated_pnl": -100.0,
                    "closed_at": b_time.isoformat()
                }
            elif tp_hit:
                return {
                    "outcome": "HIT_TP",
                    "simulated_r": 2.5,
                    "simulated_pnl": 250.0,
                    "closed_at": b_time.isoformat()
                }
        else: # SHORT
            sl_hit = sl > 0 and high >= sl
            tp_hit = tp > 0 and low <= tp

            if sl_hit and tp_hit:
                return {
                    "outcome": "HIT_SL",
                    "simulated_r": -1.0,
                    "simulated_pnl": -100.0,
                    "closed_at": b_time.isoformat()
                }
            elif sl_hit:
                return {
                    "outcome": "HIT_SL",
                    "simulated_r": -1.0,
                    "simulated_pnl": -100.0,
                    "closed_at": b_time.isoformat()
                }
            elif tp_hit:
                return {
                    "outcome": "HIT_TP",
                    "simulated_r": 2.5,
                    "simulated_pnl": 250.0,
                    "closed_at": b_time.isoformat()
                }

    # If 48 hours have passed and neither was touched
    age_hours = (now_utc - t_entry).total_seconds() / 3600.0
    if age_hours > 48.0:
        return {
            "outcome": "EXPIRED",
            "simulated_r": 0.0,
            "simulated_pnl": 0.0,
            "closed_at": t_max.isoformat()
        }

    # Still open and under 48 hours old
    return None


def run_counterfactual_backfill():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Fetch all open trades
    cursor.execute("""
        SELECT id, timestamp, account_key, symbol, direction, pattern, 
               strategy_mode, entry_price, stop_loss, take_profit_1, rejection_reasons
        FROM counterfactual_trades
        WHERE status = 'OPEN'
        ORDER BY timestamp ASC
    """)
    open_rows = [dict(r) for r in cursor.fetchall()]
    total_open = len(open_rows)
    logger.info(f"🔍 Found {total_open} OPEN shadow trades in counterfactual_trades.")

    if total_open == 0:
        logger.info("✔ No open trades to resolve.")
        conn.close()
        return

    # Determine earliest timestamp to download data
    earliest_ts = open_rows[0]["timestamp"]
    start_date = earliest_ts[:10] # 'YYYY-MM-DD'
    candle_cache = load_historical_data(start_date)

    now_utc = datetime.now(timezone.utc)
    resolved_count = 0
    wins = 0
    losses = 0
    expired = 0
    remained_open = 0

    tournament_updates = {}
    lab = ChampionChallengerLab()

    logger.info("⚙️ Evaluating open trades against historical price trajectories...")

    for trade in open_rows:
        sym = trade.get("symbol")
        if sym not in candle_cache:
            remained_open += 1
            continue

        bars = candle_cache[sym]
        resolution = resolve_trade_outcome(trade, bars, now_utc)

        if resolution:
            outcome = resolution["outcome"]
            sim_r = resolution["simulated_r"]
            sim_pnl = resolution["simulated_pnl"]
            closed_at = resolution["closed_at"]

            # Update DB
            cursor.execute("""
                UPDATE counterfactual_trades
                SET status = 'CLOSED',
                    outcome = ?,
                    simulated_r = ?,
                    simulated_pnl = ?,
                    closed_at = ?
                WHERE id = ?
            """, (outcome, sim_r, sim_pnl, closed_at, trade["id"]))

            resolved_count += 1
            if outcome == "HIT_TP":
                wins += 1
            elif outcome == "HIT_SL":
                losses += 1
            elif outcome == "EXPIRED":
                expired += 1

            # Map to tournament variant
            pattern = trade.get("pattern", "")
            var_id = CounterfactualTracker._map_pattern_to_variant_id(pattern)
            if var_id:
                if var_id not in tournament_updates:
                    tournament_updates[var_id] = {"wins": 0, "losses": 0, "total_r": 0.0, "samples": 0}
                tournament_updates[var_id]["samples"] += 1
                if outcome == "HIT_TP":
                    tournament_updates[var_id]["wins"] += 1
                    tournament_updates[var_id]["total_r"] += sim_r
                elif outcome == "HIT_SL":
                    tournament_updates[var_id]["losses"] += 1
                    tournament_updates[var_id]["total_r"] += sim_r
        else:
            remained_open += 1

    conn.commit()
    conn.close()

    # 3. Update tournament variants table
    logger.info("🏆 Updating strategy tournament variants with resolved outcomes...")
    for var_id, stats in tournament_updates.items():
        try:
            # We record each win/loss into the lab
            v = lab.variants.get(var_id)
            if v:
                v.samples += stats["samples"]
                v.wins += stats["wins"]
                v.losses += stats["losses"]
                v.total_r += stats["total_r"]
                decided = v.wins + v.losses
                v.win_rate = round((v.wins / decided * 100.0), 2) if decided > 0 else 0.0
                gross_win = v.wins * 2.5
                gross_loss = abs(v.losses * -1.0)
                v.profit_factor = round((gross_win / gross_loss), 2) if gross_loss > 0 else 2.50
                lab._save_variant(v)
                logger.info(f"  Variant {var_id:32s}: Samples={v.samples}, W={v.wins}, L={v.losses}, WR={v.win_rate}%, Net R={v.total_r:+.1f}R, PF={v.profit_factor:.2f}")
        except Exception as e:
            logger.debug(f"Error updating variant {var_id}: {e}")

    decided_trades = wins + losses
    win_rate = (wins / decided_trades * 100.0) if decided_trades > 0 else 0.0
    net_r = (wins * 2.5) + (losses * -1.0)

    print("\n" + "═" * 78)
    print(" 📊 COUNTERFACTUAL RESOLUTION BACKFILL SCORECARD")
    print("═" * 78)
    print(f" • Total Evaluated Trades : {total_open}")
    print(f" • Successfully Resolved : {resolved_count}")
    print(f"   ├─ Wins (HIT_TP +2.5R) : {wins}")
    print(f"   ├─ Losses (HIT_SL -1.0R): {losses}")
    print(f"   └─ Expired (48h Flat)  : {expired}")
    print(f" • Active Forward Trades  : {remained_open} (Under 48h active tracking)")
    print(f" • Resolved Win Rate      : {win_rate:.2f}%")
    print(f" • Net Counterfactual R   : {net_r:+.1f}R")
    print("═" * 78)
    print("✔ Backfill complete. AI RAG memory and tournament statistics synchronized.\n")


if __name__ == "__main__":
    run_counterfactual_backfill()

import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List
from src.core.database import get_db_connection

logger = logging.getLogger(__name__)

class ExecutionShadowEngine:
    """
    Execution Strategy Shadow Engine (A/B Counterfactual Tournament).
    Tracks live trades against alternative execution models in parallel:
      1. LIVE_TRAILING_RATCHET (Current Production: BE @ +1.5R, +1.0R Lock @ +2.5R)
      2. SHADOW_PARTIAL_SCALEOUT (Challenger: Bank 50% cash @ +1.5R, trail remainder to TP)
      3. SHADOW_PURE_BINARY (Baseline: 100% TP / 100% SL without trailing)
    """

    @staticmethod
    def init_db():
        """Creates table for execution tournament shadow trades if not exists."""
        try:
            conn = get_db_connection()
            conn.execute("""
                CREATE TABLE IF NOT EXISTS execution_shadow_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    entry_price REAL NOT NULL,
                    stop_loss REAL NOT NULL,
                    take_profit REAL NOT NULL,
                    risk_usd REAL DEFAULT 129.0,
                    variant_mult REAL DEFAULT 1.0,
                    peak_mfe_r REAL DEFAULT 0.0,
                    live_ratchet_r REAL DEFAULT 0.0,
                    live_ratchet_pnl REAL DEFAULT 0.0,
                    shadow_variant_pnl REAL DEFAULT 0.0,
                    shadow_partial_r REAL DEFAULT 0.0,
                    shadow_partial_pnl REAL DEFAULT 0.0,
                    shadow_binary_r REAL DEFAULT 0.0,
                    shadow_binary_pnl REAL DEFAULT 0.0,
                    status TEXT DEFAULT 'OPEN',
                    closed_at TEXT
                )
            """)
            # Safe column additions if table already existed
            try:
                conn.execute("ALTER TABLE execution_shadow_trades ADD COLUMN variant_mult REAL DEFAULT 1.0")
            except Exception:
                pass
            try:
                conn.execute("ALTER TABLE execution_shadow_trades ADD COLUMN shadow_variant_pnl REAL DEFAULT 0.0")
            except Exception:
                pass
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error initializing execution_shadow_trades table: {e}")

    def register_trade(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        risk_usd: float = 129.0,
        variant_mult: float = 1.0
    ) -> bool:
        """Registers a new active trade for multi-strategy and variant sizing shadow tracking."""
        try:
            self.init_db()
            now_iso = datetime.now(timezone.utc).isoformat()
            conn = get_db_connection()
            conn.execute("""
                INSERT INTO execution_shadow_trades (
                    timestamp, symbol, direction, entry_price, stop_loss, take_profit, risk_usd, variant_mult, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'OPEN')
            """, (now_iso, symbol, direction.upper(), entry_price, stop_loss, take_profit, risk_usd, float(variant_mult)))
            conn.commit()
            conn.close()
            logger.info(f"⚔️ [EXECUTION TOURNAMENT] Shadow Trade Registered for {symbol} {direction.upper()} @ {entry_price} (Variant Mult: {variant_mult:.2f}x)")
            return True
        except Exception as e:
            logger.error(f"Failed to register shadow tournament trade: {e}")
            return False

    def update_price(self, symbol: str, current_price: float) -> List[Dict]:
        """
        Updates live and shadow execution variant states based on current price.
        Resolves variants when targets/stops are breached.
        """
        resolved = []
        try:
            self.init_db()
            conn = get_db_connection()
            trades = conn.execute("""
                SELECT * FROM execution_shadow_trades WHERE status = 'OPEN' AND symbol = ?
            """, (symbol,)).fetchall()

            if not trades:
                conn.close()
                return resolved

            now_iso = datetime.now(timezone.utc).isoformat()

            for row in trades:
                t = dict(row)
                t_id = t["id"]
                entry = float(t["entry_price"])
                sl = float(t["stop_loss"])
                tp = float(t["take_profit"])
                risk_usd = float(t["risk_usd"])
                direction = t["direction"].upper()

                risk_dist = abs(entry - sl)
                if risk_dist <= 0:
                    continue

                # Calculate Current & Max Favorable Excursion (MFE in R)
                if direction in ["BUY", "LONG"]:
                    current_r = (current_price - entry) / risk_dist
                    hit_full_tp = current_price >= tp
                    hit_initial_sl = current_price <= sl
                else: # SELL / SHORT
                    current_r = (entry - current_price) / risk_dist
                    hit_full_tp = current_price <= tp
                    hit_initial_sl = current_price >= sl

                peak_mfe = max(float(t.get("peak_mfe_r", 0.0) or 0.0), current_r)

                # Total target R multiple
                tp_r = abs(tp - entry) / risk_dist

                # ── Evaluate Outcome for Strategy 1: LIVE TRAILING RATCHET ──
                # BE @ +1.5R, +1.0R lock @ +2.5R (or 80% TP)
                live_r = 0.0
                if hit_full_tp:
                    live_r = tp_r
                elif hit_initial_sl:
                    if peak_mfe >= 2.5 or (tp_r > 0 and peak_mfe >= 0.80 * tp_r):
                        live_r = 1.0  # Stopped at +1.0R lock
                    elif peak_mfe >= 1.5:
                        live_r = 0.0  # Stopped at Break-Even
                    else:
                        live_r = -1.0 # Stopped at Initial SL

                # ── Evaluate Outcome for Strategy 2: SHADOW PARTIAL SCALE-OUT ──
                # Bank 50% @ +1.5R (+0.75R realized), trail remainder with BE @ 1.5R, Lock @ 2.5R, TP @ tp_r
                partial_r = 0.0
                if hit_full_tp:
                    # 50% @ 1.5R (+0.75R) + 50% @ tp_r (+0.5 * tp_r)
                    partial_r = 0.75 + (0.5 * tp_r)
                elif hit_initial_sl:
                    if peak_mfe >= 2.5 or (tp_r > 0 and peak_mfe >= 0.80 * tp_r):
                        # 50% @ 1.5R (+0.75R) + 50% @ 1.0R lock (+0.50R)
                        partial_r = 0.75 + 0.50 # +1.25R
                    elif peak_mfe >= 1.5:
                        # 50% @ 1.5R (+0.75R) + 50% @ Break-Even (+0.0R)
                        partial_r = 0.75
                    else:
                        partial_r = -1.0 # Initial SL

                # ── Evaluate Outcome for Strategy 3: SHADOW PURE BINARY ──
                # Full TP or Full SL only
                binary_r = 0.0
                if hit_full_tp:
                    binary_r = tp_r
                elif hit_initial_sl:
                    binary_r = -1.0

                # Check if trade is fully resolved
                is_closed = hit_full_tp or hit_initial_sl

                if is_closed:
                    variant_mult = float(t.get("variant_mult", 1.0) or 1.0)
                    variant_pnl = live_r * (risk_usd * variant_mult)

                    conn.execute("""
                        UPDATE execution_shadow_trades
                        SET peak_mfe_r = ?,
                            live_ratchet_r = ?, live_ratchet_pnl = ?,
                            shadow_variant_pnl = ?,
                            shadow_partial_r = ?, shadow_partial_pnl = ?,
                            shadow_binary_r = ?, shadow_binary_pnl = ?,
                            status = 'CLOSED', closed_at = ?
                        WHERE id = ?
                    """, (
                        peak_mfe,
                        live_r, live_r * risk_usd,
                        variant_pnl,
                        partial_r, partial_r * risk_usd,
                        binary_r, binary_r * risk_usd,
                        now_iso, t_id
                    ))
                    resolved.append({
                        "id": t_id, "symbol": symbol,
                        "live_ratchet_r": live_r, "shadow_partial_r": partial_r, "shadow_binary_r": binary_r,
                        "variant_mult": variant_mult, "variant_pnl": variant_pnl
                    })
                    logger.info(f"🏁 [EXECUTION TOURNAMENT RESOLVED] {symbol}: Live={live_r:+.2f}R (${live_r * risk_usd:+.2f}) | Variant Sizing ({variant_mult:.2f}x)=${variant_pnl:+.2f} | Shadow Partial={partial_r:+.2f}R | Binary={binary_r:+.2f}R")
                else:
                    # Update peak MFE in flight
                    conn.execute("""
                        UPDATE execution_shadow_trades SET peak_mfe_r = ? WHERE id = ?
                    """, (peak_mfe, t_id))

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error updating execution shadow engine price: {e}")

        return resolved

    @staticmethod
    def get_leaderboard() -> Dict:
        """Returns cumulative statistics comparing execution models and sizing modes."""
        try:
            ExecutionShadowEngine.init_db()
            conn = get_db_connection()
            rows = conn.execute("""
                SELECT live_ratchet_r, live_ratchet_pnl,
                       shadow_variant_pnl,
                       shadow_partial_r, shadow_partial_pnl,
                       shadow_binary_r, shadow_binary_pnl,
                       status
                FROM execution_shadow_trades
                WHERE status = 'CLOSED'
            """).fetchall()
            conn.close()

            if not rows:
                return {
                    "total_trades": 0,
                    "live_ratchet": {},
                    "shadow_variant_sizing": {},
                    "shadow_partial": {},
                    "shadow_binary": {}
                }

            total = len(rows)
            live_r = sum(float(r["live_ratchet_r"]) for r in rows)
            live_pnl = sum(float(r["live_ratchet_pnl"]) for r in rows)
            live_wins = sum(1 for r in rows if float(r["live_ratchet_r"]) > 0)

            variant_pnl = sum(float(r["shadow_variant_pnl"] or 0.0) for r in rows)

            partial_r = sum(float(r["shadow_partial_r"]) for r in rows)
            partial_pnl = sum(float(r["shadow_partial_pnl"]) for r in rows)
            partial_wins = sum(1 for r in rows if float(r["shadow_partial_r"]) > 0)

            binary_r = sum(float(r["shadow_binary_r"]) for r in rows)
            binary_pnl = sum(float(r["shadow_binary_pnl"]) for r in rows)
            binary_wins = sum(1 for r in rows if float(r["shadow_binary_r"]) > 0)

            return {
                "total_trades": total,
                "live_ratchet": {
                    "total_r": round(live_r, 2), "total_pnl": round(live_pnl, 2),
                    "win_rate": round((live_wins / total) * 100, 1) if total > 0 else 0.0
                },
                "shadow_variant_sizing": {
                    "total_pnl": round(variant_pnl, 2),
                    "edge_vs_flat_usd": round(variant_pnl - live_pnl, 2)
                },
                "shadow_partial": {
                    "total_r": round(partial_r, 2), "total_pnl": round(partial_pnl, 2),
                    "win_rate": round((partial_wins / total) * 100, 1) if total > 0 else 0.0
                },
                "shadow_binary": {
                    "total_r": round(binary_r, 2), "total_pnl": round(binary_pnl, 2),
                    "win_rate": round((binary_wins / total) * 100, 1) if total > 0 else 0.0
                },
                "alpha_edge_usd": round(live_pnl - partial_pnl, 2)
            }
        except Exception as e:
            logger.error(f"Error fetching execution tournament leaderboard: {e}")
            return {}

import json
import logging
from datetime import datetime, timezone
from src.core.database import get_db_connection

logger = logging.getLogger(__name__)

class CounterfactualTracker:
    """
    Counterfactual Shadow Agent Tracking Engine.
    Tracks candidate setups rejected by specific account filter combinations
    and simulates their trade outcome to evaluate filter efficiency.
    """
    def __init__(self):
        pass

    def register_shadow_trade(
        self,
        setup: dict,
        account_key: str,
        strategy_mode: str,
        rejection_reasons: list
    ) -> bool:
        """Logs a rejected setup as a counterfactual shadow trade."""
        if not setup or not account_key or not rejection_reasons:
            return False

        try:
            symbol = setup.get("symbol", "BTC/USD")
            direction = setup.get("direction", setup.get("bias", "BUY")).upper()
            pattern = setup.get("pattern", setup.get("formations", "UNKNOWN"))
            entry_price = float(setup.get("price", setup.get("entry_price", 0.0)))
            stop_loss = float(setup.get("stop_loss", 0.0))
            tp1 = float(setup.get("take_profit", setup.get("tp1", 0.0)))
            tp2 = float(setup.get("tp2", 0.0))

            if entry_price <= 0 or stop_loss <= 0:
                return False

            now_iso = datetime.now(timezone.utc).isoformat()
            reasons_json = json.dumps(rejection_reasons)

            conn = get_db_connection()
            conn.execute(
                """
                INSERT INTO counterfactual_trades (
                    timestamp, account_key, symbol, direction, pattern, strategy_mode,
                    entry_price, stop_loss, take_profit_1, take_profit_2,
                    rejection_reasons, status, outcome, simulated_pnl, simulated_r
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'OPEN', 'PENDING', 0.0, 0.0)
                """,
                (
                    now_iso, account_key, symbol, direction, pattern, strategy_mode,
                    entry_price, stop_loss, tp1, tp2, reasons_json
                )
            )
            conn.commit()
            conn.close()
            logger.info(f"👻 Counterfactual Shadow Agent registered for {account_key} ({symbol} {direction}): {reasons_json}")
            return True
        except Exception as e:
            logger.error(f"Failed to register counterfactual shadow trade: {e}")
            return False

    def evaluate_open_shadow_trades(self, scanner) -> int:
        """
        Evaluates open counterfactual shadow trades against live price action.
        Returns the number of resolved trades.
        """
        try:
            conn = get_db_connection()
            open_trades = conn.execute(
                "SELECT * FROM counterfactual_trades WHERE status = 'OPEN'"
            ).fetchall()

            if not open_trades:
                conn.close()
                return 0

            resolved_count = 0
            now_utc = datetime.now(timezone.utc)

            for row in open_trades:
                t = dict(row)
                t_id = t["id"]
                symbol = t["symbol"]
                direction = t["direction"]
                entry = float(t["entry_price"])
                sl = float(t["stop_loss"])
                tp = float(t["take_profit_1"])

                # Fetch recent bars
                df = scanner.fetch_data(symbol, "5m", limit=30)
                if df is None or df.empty:
                    continue

                recent_high = float(df["high"].max())
                recent_low = float(df["low"].min())
                last_price = float(df["close"].iloc[-1])

                created_at = datetime.fromisoformat(t["timestamp"].replace("Z", "+00:00"))
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)

                age_hours = (now_utc - created_at).total_seconds() / 3600.0

                outcome = None
                pnl = 0.0
                r_mult = 0.0

                if direction in ["BUY", "LONG"]:
                    if tp > 0 and recent_high >= tp:
                        outcome = "HIT_TP"
                        r_mult = 2.5
                        pnl = 250.0
                    elif sl > 0 and recent_low <= sl:
                        outcome = "HIT_SL"
                        r_mult = -1.0
                        pnl = -100.0
                else: # SELL / SHORT
                    if tp > 0 and recent_low <= tp:
                        outcome = "HIT_TP"
                        r_mult = 2.5
                        pnl = 250.0
                    elif sl > 0 and recent_high >= sl:
                        outcome = "HIT_SL"
                        r_mult = -1.0
                        pnl = -100.0

                # Auto-expire stale shadow trades after 48h
                if not outcome and age_hours > 48:
                    outcome = "EXPIRED"
                    r_mult = 0.0
                    pnl = 0.0

                if outcome:
                    resolved_count += 1
                    closed_iso = now_utc.isoformat()
                    conn.execute(
                        """
                        UPDATE counterfactual_trades
                        SET status = 'CLOSED', outcome = ?, simulated_pnl = ?, simulated_r = ?, closed_at = ?
                        WHERE id = ?
                        """,
                        (outcome, pnl, r_mult, closed_iso, t_id)
                    )
                    logger.info(f"🏁 Counterfactual Trade #{t_id} [{t['account_key']}] Resolved: {outcome} (${pnl:+.2f}, {r_mult:+.1f}R)")

            conn.commit()
            conn.close()
            return resolved_count
        except Exception as e:
            logger.error(f"Error evaluating open shadow trades: {e}")
            return 0

    @staticmethod
    def get_counterfactual_summary() -> dict:

        """Aggregates counterfactual performance metrics across accounts and filter types."""
        try:
            conn = get_db_connection()
            rows = conn.execute("SELECT * FROM counterfactual_trades").fetchall()
            conn.close()

            summary = {
                "total_shadow_trades": len(rows),
                "by_account": {},
                "by_filter": {}
            }

            for row in rows:
                r = dict(row)
                acc = r["account_key"]
                outcome = r["outcome"]
                pnl = float(r["simulated_pnl"] or 0.0)
                reasons = json.loads(r["rejection_reasons"] or "[]")

                if acc not in summary["by_account"]:
                    summary["by_account"][acc] = {"total": 0, "hits_tp": 0, "hits_sl": 0, "net_pnl": 0.0}

                summary["by_account"][acc]["total"] += 1
                if outcome == "HIT_TP":
                    summary["by_account"][acc]["hits_tp"] += 1
                elif outcome == "HIT_SL":
                    summary["by_account"][acc]["hits_sl"] += 1
                summary["by_account"][acc]["net_pnl"] += pnl

                for reason in reasons:
                    # Clean reason name e.g. HURST_CHAOS_GATE
                    filter_name = reason.split("(")[0].strip()
                    if filter_name not in summary["by_filter"]:
                        summary["by_filter"][filter_name] = {"total": 0, "hits_tp": 0, "hits_sl": 0, "net_pnl": 0.0}
                    summary["by_filter"][filter_name]["total"] += 1
                    if outcome == "HIT_TP":
                        summary["by_filter"][filter_name]["hits_tp"] += 1
                    elif outcome == "HIT_SL":
                        summary["by_filter"][filter_name]["hits_sl"] += 1
                    summary["by_filter"][filter_name]["net_pnl"] += pnl

            return summary
        except Exception as e:
            logger.error(f"Failed to generate counterfactual summary: {e}")
            return {}

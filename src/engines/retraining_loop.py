"""
Automated Retraining Loop
==========================
Compounds the system's edge by weekly retraining the AI model on
outcomes from the signed trade ledger.

What it does:
  1. Every Sunday at 00:00 UTC, extracts the past week's closed trades
     from the signed_ledger table (verified signals only, no rogue trades)
  2. Labels each trade: WIN / LOSS / BREAKEVEN
  3. Builds a structured training dataset (signal context → outcome)
  4. Fine-tunes the local Gemini context window via few-shot prompt injection
     (No Vertex AI required — uses the existing Gemini API with richer context)
  5. Optionally exports to JSONL for formal fine-tuning on Google Vertex AI
  6. Logs the retrain event so you can audit improvement over time

Architecture:
  - "Soft retraining": Updates the in-memory few-shot examples used by
    AIValidator every scan cycle. Zero cost. Happens automatically.
  - "Hard retraining": Exports a JSONL dataset to /data/training/ for
    formal Vertex AI fine-tuning. Triggered manually or on schedule.

The key insight: the signed ledger is your ground truth. Every signed
signal has an outcome stamped back onto it. Over time this becomes a
self-improving feedback loop — the model learns what YOUR market and
YOUR patterns actually produce in live trading.
"""

import os
import json
import logging
import sqlite3
from datetime import datetime, timezone, timedelta, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
from src.core.config import Config
TRAINING_DATA_DIR = Path(os.path.dirname(Config.DB_PATH)).parent / "data" / "training"
TRAINING_DATA_DIR.mkdir(parents=True, exist_ok=True)

RETRAINING_LOG_PATH = TRAINING_DATA_DIR / "retraining_log.json"
FEW_SHOT_CACHE_PATH = TRAINING_DATA_DIR / "few_shot_examples.json"

# ── Minimum samples needed before retraining ─────────────────────────────────
MIN_SAMPLES_FOR_RETRAIN = 5   # Don't retrain on <5 new outcomes
MAX_FEW_SHOT_EXAMPLES   = 20  # Keep the N best examples in the live cache


class RetrainingLoop:
    """
    Weekly retraining loop. Reads from signed_ledger, builds training data,
    and updates the few-shot cache used by AIValidator.

    Usage:
        loop = RetrainingLoop()
        # Called automatically by local_scanner.py each Sunday
        loop.run_if_due()
        # Or force a run:
        loop.run(force=True)
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or Config.DB_PATH
        self._last_run: Optional[datetime] = self._load_last_run()

    def _load_last_run(self) -> Optional[datetime]:
        """Reads last retrain timestamp from log file."""
        if not RETRAINING_LOG_PATH.exists():
            return None
        try:
            with open(RETRAINING_LOG_PATH) as f:
                log = json.load(f)
                last = log.get('last_run_utc')
                return datetime.fromisoformat(last) if last else None
        except Exception:
            return None

    def _save_run_log(self, summary: dict):
        """Persists retraining run metadata."""
        log = {
            'last_run_utc': datetime.now(timezone.utc).isoformat(),
            'runs': []
        }
        if RETRAINING_LOG_PATH.exists():
            try:
                with open(RETRAINING_LOG_PATH) as f:
                    log = json.load(f)
            except Exception:
                pass

        log['last_run_utc'] = datetime.now(timezone.utc).isoformat()
        log.setdefault('runs', []).append(summary)
        log['runs'] = log['runs'][-52:]  # Keep 52 weeks of history

        with open(RETRAINING_LOG_PATH, 'w') as f:
            json.dump(log, f, indent=2)

    def _is_due(self) -> bool:
        """Returns True if 7+ days have passed since last retrain."""
        if self._last_run is None:
            return True
        elapsed = datetime.now(timezone.utc) - self._last_run
        return elapsed.total_seconds() >= 7 * 24 * 3600

    def _fetch_recent_outcomes(self, days_back: int = 7) -> list[dict]:
        """
        Queries signed_ledger for closed, non-rogue trades in the last N days.
        Returns only records with a known outcome (WIN/LOSS/BREAKEVEN).
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()
        try:
            rows = conn.execute("""
                SELECT *
                FROM signed_ledger
                WHERE is_rogue = 0
                  AND outcome NOT IN ('PENDING', 'UNKNOWN')
                  AND timestamp >= ?
                ORDER BY timestamp DESC
            """, (cutoff,)).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.warning(f"[Retraining] Could not fetch outcomes: {e}")
            return []
        finally:
            conn.close()

    def _build_few_shot_example(self, record: dict) -> dict:
        """
        Converts a ledger record into a few-shot training example.
        Format matches what AIValidator sends to Gemini.
        """
        outcome = record.get('outcome', 'UNKNOWN')
        pnl     = record.get('pnl', 0.0) or 0.0
        
        # Phase 2: Extract enriched context
        vol_spike = record.get('volume_spike', 1.0)
        smt = record.get('true_smt') or "None"
        regime = record.get('shadow_regime') or "Unknown"

        # Build a compact prompt/completion pair
        prompt = (
            f"Symbol: {record['symbol']} | "
            f"Direction: {record['direction']} | "
            f"Pattern: {record['pattern']} | "
            f"AI Score: {record['ai_score']}/10 | "
            f"Regime: {regime} | "
            f"Vol Spike: {vol_spike}x | "
            f"SMT: {smt}"
        )

        # What actually happened — this is the ground truth label
        if outcome == 'WIN':
            label = f"Trade was a WINNER. PnL: +${pnl:.2f}. Signal validated by live market. Volume/SMT confluence confirmed institutional sponsorship."
            score_adjustment = +0.5  # Upvote
        elif outcome == 'LOSS':
            label = f"Trade was a LOSS. PnL: -${abs(pnl):.2f}. Pattern failed. Check if volume spike or SMT was insufficient for this regime."
            score_adjustment = -0.5  # Downvote
        elif outcome == 'BREAKEVEN':
            label = f"Trade broke even. PnL: ${pnl:.2f}. Partial validation."
            score_adjustment = 0.0
        else:
            return None

        return {
            'signal_id':        record['signal_id'],
            'timestamp':        record['timestamp'],
            'symbol':           record['symbol'],
            'direction':        record['direction'],
            'pattern':          record['pattern'],
            'ai_score':         record['ai_score'],
            'outcome':          outcome,
            'pnl':              pnl,
            'prompt':           prompt,
            'label':            label,
            'score_adjustment': score_adjustment,
            'regime':           regime,
            'vol_spike':        vol_spike,
            'true_smt':         smt
        }

    def _export_jsonl(self, examples: list[dict]) -> Path:
        """
        Exports training examples in Vertex AI fine-tuning JSONL format.
        Optimized for Phase 2 instruction-tuning.
        """
        date_str = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')
        out_path = TRAINING_DATA_DIR / f"training_{date_str}.jsonl"

        with open(out_path, 'w') as f:
            for ex in examples:
                if not ex:
                    continue
                record = {
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                f"Evaluate this institutional setup:\n{ex['prompt']}\n\n"
                                f"Outcome: This setup resulted in a {ex['outcome']} ({ex['label']}).\n\n"
                                f"Instruction: Calibrate your weighting of Vol Spike and SMT for the '{ex['regime']}' regime."
                            )
                        },
                        {
                            "role": "model",
                            "content": (
                                f"Live Audit: {ex['label']} "
                                f"Adjustment: {ex['score_adjustment']:+.1f}. "
                                f"In {ex['regime']} regimes, the {ex['pattern']} requires "
                                f"strict adherence to institutional prints (Vol: {ex['vol_spike']}x, SMT: {ex['true_smt']})."
                            )
                        }
                    ]
                }
                f.write(json.dumps(record) + '\n')

        logger.info(f"[Retraining] 📁 JSONL exported: {out_path} ({len(examples)} examples)")
        return out_path

    def _update_few_shot_cache(self, examples: list[dict]):
        """
        Merges new examples into the few-shot cache.
        Keeps the MAX_FEW_SHOT_EXAMPLES best examples (wins first, losses for calibration).
        """
        existing = []
        if FEW_SHOT_CACHE_PATH.exists():
            try:
                with open(FEW_SHOT_CACHE_PATH) as f:
                    existing = json.load(f)
            except Exception:
                existing = []

        # Merge and deduplicate by signal_id
        all_examples = {e['signal_id']: e for e in existing}
        for ex in examples:
            if ex:
                all_examples[ex['signal_id']] = ex

        # Sort: wins first (for positive reinforcement), then losses (calibration)
        sorted_examples = sorted(
            all_examples.values(),
            key=lambda x: (x['outcome'] == 'WIN', abs(x['pnl'] or 0)),
            reverse=True
        )[:MAX_FEW_SHOT_EXAMPLES]

        with open(FEW_SHOT_CACHE_PATH, 'w') as f:
            json.dump(sorted_examples, f, indent=2)

        logger.info(f"[Retraining] 🧠 Few-shot cache updated: {len(sorted_examples)} examples active.")

    def get_few_shot_context(self) -> str:
        """
        Returns a formatted string of best examples for injection into AIValidator prompts.
        Called every scan cycle to enrich AI context with live outcomes.
        """
        if not FEW_SHOT_CACHE_PATH.exists():
            return ""

        try:
            with open(FEW_SHOT_CACHE_PATH) as f:
                examples = json.load(f)
        except Exception:
            return ""

        if not examples:
            return ""

        lines = ["── LIVE OUTCOME CALIBRATION (from signed trade ledger) ──"]
        for ex in examples[:10]:  # Use top 10 for prompt context
            emoji = "✅" if ex['outcome'] == 'WIN' else ("❌" if ex['outcome'] == 'LOSS' else "➖")
            lines.append(
                f"{emoji} {ex['outcome']}: {ex['symbol']} {ex['direction']} "
                f"({ex['pattern']}) | AI={ex['ai_score']}/10 | PnL=${ex['pnl']:+.2f}"
            )

        lines.append("── Use these live outcomes to calibrate your confidence score ──")
        return '\n'.join(lines)

    def run(self, force: bool = False, export_jsonl: bool = True) -> dict:
        """
        Executes the retraining loop.

        Args:
            force:       Skip due-date check and run now
            export_jsonl: Also export JSONL for Vertex AI fine-tuning

        Returns:
            Summary dict
        """
        if not force and not self._is_due():
            days_until = 7 - (datetime.now(timezone.utc) - self._last_run).days if self._last_run else 0
            logger.info(f"[Retraining] ⏭️ Not due yet. Next retrain in ~{days_until} day(s).")
            return {'status': 'skipped', 'reason': 'not_due'}

        logger.info("🔁 [Retraining] Starting automated retraining cycle...")
        start = datetime.now(timezone.utc)

        # 1. Fetch recent outcomes from signed ledger
        records = self._fetch_recent_outcomes(days_back=7)
        logger.info(f"[Retraining] Found {len(records)} closed trades from past 7 days.")

        if len(records) < MIN_SAMPLES_FOR_RETRAIN:
            msg = f"Only {len(records)} outcomes — minimum {MIN_SAMPLES_FOR_RETRAIN} required. Skipping."
            logger.info(f"[Retraining] ⚠️ {msg}")
            return {'status': 'skipped', 'reason': 'insufficient_data', 'count': len(records)}

        # 2. Build training examples
        examples = [self._build_few_shot_example(r) for r in records]
        examples = [e for e in examples if e]  # Filter None

        wins   = sum(1 for e in examples if e['outcome'] == 'WIN')
        losses = sum(1 for e in examples if e['outcome'] == 'LOSS')
        avg_pnl = sum(e['pnl'] for e in examples) / len(examples) if examples else 0

        logger.info(f"[Retraining] W/L: {wins}/{losses} | Avg PnL: ${avg_pnl:+.2f}")

        # 3. Update the live few-shot cache (zero cost, immediate effect)
        self._update_few_shot_cache(examples)

        # 4. Export JSONL for formal fine-tuning (optional)
        jsonl_path = None
        if export_jsonl:
            jsonl_path = str(self._export_jsonl(examples))

        elapsed = (datetime.now(timezone.utc) - start).total_seconds()

        summary = {
            'status':         'success',
            'run_at_utc':     start.isoformat(),
            'elapsed_secs':   elapsed,
            'samples':        len(examples),
            'wins':           wins,
            'losses':         losses,
            'win_rate':       wins / len(examples) if examples else 0,
            'avg_pnl':        avg_pnl,
            'few_shot_cache': str(FEW_SHOT_CACHE_PATH),
            'jsonl_export':   jsonl_path,
        }

        self._save_run_log(summary)
        self._last_run = start

        logger.info(
            f"✅ [Retraining] Complete — {len(examples)} examples | "
            f"WR: {wins}/{len(examples)} ({wins/len(examples)*100:.0f}%) | "
            f"Avg PnL: ${avg_pnl:+.2f} | Elapsed: {elapsed:.1f}s"
        )
        return summary

    def run_if_due(self) -> dict:
        """Convenience method — only runs if the 7-day schedule is met."""
        return self.run(force=False)

    def force_run(self) -> dict:
        """Force an immediate retraining cycle regardless of schedule."""
        return self.run(force=True)

"""
Export Training Data for Vertex AI Fine-Tuning
===============================================
Converts resolved scans into Vertex AI JSONL format.

Format (Gemini supervised fine-tuning):
  {"messages": [
    {"role": "user", "content": "<setup narrative>"},
    {"role": "model", "content": "WIN or LOSS"}
  ]}

Run: python3 scripts/export_training_data.py
Output: data/training/sovereign_trades.jsonl
"""
import os
import sys
import json
import logging
from datetime import datetime

sys.path.append(os.getcwd())

from src.core.supabase_client import supabase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TrainingExporter")

OUTPUT_DIR = "data/training"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "sovereign_trades.jsonl")

SYSTEM_PROMPT = """You are the Sovereign Trading Oracle — a precision execution model trained exclusively on institutional ICT/SMC patterns. 
Given a trade setup description, determine if this setup will WIN (hit 3R target) or LOSS (hit stop loss first).
Consider: session timing, SMT strength, market regime, pattern quality, and Asian Range context.
Answer with exactly one word: WIN or LOSS."""

def build_narrative(scan):
    """Converts a scan record into a rich text narrative for training."""
    symbol = scan.get('symbol', 'Unknown')
    pattern = scan.get('pattern', 'Unknown')
    bias = scan.get('bias', 'Unknown')
    ai_score = scan.get('ai_score', 0)
    regime = scan.get('shadow_regime', 'Unknown')
    reasoning = scan.get('ai_reasoning', '')
    
    # Parse timestamp to get session
    ts_str = scan.get('timestamp', '')
    session = 'Unknown'
    try:
        ts = datetime.fromisoformat(ts_str.replace('Z', '').split('+')[0])
        hour_utc = ts.hour
        if 4 <= hour_utc < 7:
            session = 'Asian Fade Window (PRIME)'
        elif 7 <= hour_utc < 10:
            session = 'London Open'
        elif 12 <= hour_utc < 20:
            session = 'New York Session'
        elif 0 <= hour_utc < 4:
            session = 'Asian Session'
        else:
            session = 'Off-Hours'
    except Exception:
        pass

    narrative = (
        f"Symbol: {symbol} | Direction: {bias}\n"
        f"Pattern: {pattern}\n"
        f"Session: {session}\n"
        f"AI Confidence Score: {ai_score}/10\n"
        f"Market Regime: {regime}\n"
    )

    if reasoning:
        narrative += f"AI Analysis: {reasoning[:300]}"

    return narrative.strip()

def export_training_data(min_score=5.0, outcomes=('WIN', 'LOSS')):
    if not supabase.client:
        logger.error("Supabase not connected.")
        return

    logger.info("📤 Fetching resolved scans for training export...")

    res = supabase.client.table('scans')\
        .select('*')\
        .in_('outcome', list(outcomes))\
        .gte('ai_score', min_score)\
        .order('timestamp', desc=True)\
        .limit(2000)\
        .execute()

    scans = res.data or []
    
    # 🌟 NEW: Fetch successful journal entries as "WIN" examples
    logger.info("👤 Fetching Human Alpha (Journal) for training export...")
    journal_res = supabase.client.table('journal')\
        .select('*')\
        .gt('pnl', 0)\
        .order('timestamp', desc=True)\
        .limit(200)\
        .execute()
    
    journal_entries = journal_res.data or []
    
    logger.info(f"📦 Found {len(scans)} bot scans and {len(journal_entries)} human alpha wins.")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    examples = []
    win_count = 0
    loss_count = 0

    # Process Bot Scans
    for scan in scans:
        outcome = scan.get('outcome')
        narrative = build_narrative(scan)
        example = {
            "system_instruction": {
                "role": "system",
                "parts": [{"text": SYSTEM_PROMPT}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": narrative}]
                },
                {
                    "role": "model",
                    "parts": [{"text": outcome}]
                }
            ]
        }
        examples.append(example)
        if outcome == 'WIN': win_count += 1
        else: loss_count += 1

    # Process Human Alpha (Journal) -> All are WINs
    for trade in journal_entries:
        # Create a simplified narrative for manual trades
        narrative = (
            f"Symbol: {trade.get('symbol')} | Direction: {trade.get('side')}\n"
            f"Pattern: Discretionary Alpha\n"
            f"Session: Human Optimized\n"
            f"AI Analysis: {trade.get('mentor_feedback', 'High performance manual trade.')[:300]}"
        )
        example = {
            "system_instruction": {
                "role": "system",
                "parts": [{"text": SYSTEM_PROMPT}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": narrative}]
                },
                {
                    "role": "model",
                    "parts": [{"text": "WIN"}]
                }
            ]
        }
        examples.append(example)
        win_count += 1

    # Write JSONL
    with open(OUTPUT_FILE, 'w') as f:
        for ex in examples:
            f.write(json.dumps(ex) + '\n')

    logger.info(f"✅ Exported {len(examples)} training examples → {OUTPUT_FILE}")
    logger.info(f"   WIN: {win_count} | LOSS: {loss_count}")
    logger.info(f"   Improved Win Rate in training data: {win_count/len(examples)*100:.1f}%")
    
    # Also write a stats summary
    stats = {
        "generated_at": datetime.utcnow().isoformat(),
        "total_examples": len(examples),
        "wins": win_count,
        "losses": loss_count,
        "win_rate_pct": round(win_count / len(examples) * 100, 1) if examples else 0,
        "output_file": OUTPUT_FILE
    }
    with open(os.path.join(OUTPUT_DIR, "training_stats.json"), 'w') as f:
        json.dump(stats, f, indent=2)

    print(f"\n🎯 Ready for Vertex AI. Next step:\n   python3 scripts/vertex_finetune.py")

if __name__ == "__main__":
    export_training_data()

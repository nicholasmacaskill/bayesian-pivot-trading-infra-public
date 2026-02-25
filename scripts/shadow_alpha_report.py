"""
Shadow Alpha Report
====================
Detects "missed alpha" — scans the AI rejected that would have hit target.

This is your most powerful source of ongoing edge discovery:
  - If a pattern consistently appears as MISSED ALPHA, you have an untapped edge
  - Run weekly to audit AI performance and discover systematic biases
  - Optionally fires Telegram alerts for actionable missed opportunities

Run: python3 scripts/shadow_alpha_report.py
     python3 scripts/shadow_alpha_report.py --alert  (sends Telegram)
"""
import os
import sys
import json
import logging
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.append(os.getcwd())

from src.core.supabase_client import supabase
from dotenv import load_dotenv

load_dotenv('.env.local')
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ShadowAlpha")

AI_THRESHOLD = 8.0  # Standard gate used in production

def fetch_shadow_opportunities(days_back=30):
    """
    Fetches scans that:
    - Were REJECTED by the AI (score < threshold OR verdict contains REJECT)
    - But resolved as WIN (would have hit the target)
    """
    if not supabase.client:
        logger.error("Supabase not connected.")
        return []

    cutoff = (datetime.utcnow() - timedelta(days=days_back)).isoformat()

    res = supabase.client.table('scans') \
        .select('*') \
        .eq('outcome', 'WIN') \
        .lt('ai_score', AI_THRESHOLD) \
        .gte('timestamp', cutoff) \
        .order('timestamp', desc=True) \
        .execute()

    return res.data or []

def fetch_accepted_performance(days_back=30):
    """Fetches scans the AI accepted and their outcomes."""
    if not supabase.client:
        return []

    cutoff = (datetime.utcnow() - timedelta(days=days_back)).isoformat()

    res = supabase.client.table('scans') \
        .select('*') \
        .gte('ai_score', AI_THRESHOLD) \
        .in_('outcome', ['WIN', 'LOSS']) \
        .gte('timestamp', cutoff) \
        .order('timestamp', desc=True) \
        .execute()

    return res.data or []

def analyze_missed_alpha(missed):
    """Groups missed opportunities by pattern, session, symbol."""
    by_pattern = defaultdict(list)
    by_symbol = defaultdict(list)
    by_session = defaultdict(list)

    for scan in missed:
        pattern = scan.get('pattern', 'Unknown')
        symbol = scan.get('symbol', 'Unknown')
        actual_r = scan.get('actual_r', 0) or 0

        by_pattern[pattern].append(actual_r)
        by_symbol[symbol].append(actual_r)

        # Bin by UTC hour
        ts_str = scan.get('timestamp', '')
        try:
            ts = datetime.fromisoformat(ts_str.replace('Z', '').split('+')[0])
            hour = ts.hour
            if 4 <= hour < 7:
                session = "Asian Fade (PRIME)"
            elif 7 <= hour < 10:
                session = "London Open"
            elif 12 <= hour < 20:
                session = "New York"
            else:
                session = "Asian Session"
        except Exception:
            session = "Unknown"

        by_session[session].append(actual_r)

    return by_pattern, by_symbol, by_session

def print_report(missed, accepted):
    print("\n" + "="*60)
    print("⚠️  SOVEREIGN SHADOW ALPHA REPORT")
    print("="*60)

    if not missed:
        print("✅ No significant missed alpha found in this period.")
    else:
        print(f"\n🔴 MISSED OPPORTUNITIES: {len(missed)} winning trades REJECTED by AI")

        by_pattern, by_symbol, by_session = analyze_missed_alpha(missed)

        print("\n📊 Top Missed Patterns (AI said NO, market said YES):")
        sorted_patterns = sorted(by_pattern.items(), key=lambda x: sum(x[1]), reverse=True)
        for pattern, rs in sorted_patterns[:8]:
            avg_r = sum(rs) / len(rs)
            print(f"  {pattern:45s}  x{len(rs)} wins  avg {avg_r:.1f}R")

        print("\n📊 By Symbol:")
        for symbol, rs in sorted(by_symbol.items(), key=lambda x: len(x[1]), reverse=True):
            print(f"  {symbol:<15} {len(rs)} missed wins")

        print("\n📊 By Session:")
        for session, rs in sorted(by_session.items(), key=lambda x: len(x[1]), reverse=True):
            avg_r = sum(rs) / len(rs)
            print(f"  {session:<30} {len(rs)} misses  avg {avg_r:.1f}R")

    if accepted:
        wins = [s for s in accepted if s.get('outcome') == 'WIN']
        losses = [s for s in accepted if s.get('outcome') == 'LOSS']
        wr = len(wins) / len(accepted) * 100 if accepted else 0
        print(f"\n✅ AI-ACCEPTED TRADES: {len(accepted)} total")
        print(f"   Win Rate: {wr:.1f}%  ({len(wins)} wins / {len(losses)} losses)")

    # Highlight biggest opportunity
    if missed:
        best = max(missed, key=lambda x: x.get('actual_r', 0) or 0)
        print(f"\n💡 Best Missed Trade: [{best.get('symbol')}] {best.get('pattern')}")
        print(f"   Would have returned {best.get('actual_r', 0):.1f}R | AI Score: {best.get('ai_score')}")

    print("\n" + "="*60)

def send_telegram_report(missed):
    """Sends a Telegram summary of missed alpha."""
    if not missed:
        return
    
    from src.clients.telegram_notifier import TelegramNotifier
    notifier = TelegramNotifier()

    top_patterns = defaultdict(int)
    for s in missed:
        top_patterns[s.get('pattern', 'Unknown')] += 1

    top_3 = sorted(top_patterns.items(), key=lambda x: x[1], reverse=True)[:3]

    message = (
        f"⚠️ *SHADOW ALPHA REPORT*\n\n"
        f"🔴 *{len(missed)} winning trades were REJECTED by the AI*\n\n"
        f"*Top Missed Patterns:*\n"
    )
    for pattern, count in top_3:
        message += f"  • {pattern}: {count}x\n"

    message += f"\n_Run `python3 scripts/shadow_alpha_report.py` for full breakdown._"
    notifier._send_message(message)
    logger.info("📨 Telegram report sent.")

def main():
    days = 30
    send_alert = "--alert" in sys.argv

    logger.info(f"🔍 Analyzing last {days} days of scans...")
    missed = fetch_shadow_opportunities(days_back=days)
    accepted = fetch_accepted_performance(days_back=days)

    print_report(missed, accepted)

    # Save to JSON
    os.makedirs("data", exist_ok=True)
    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "period_days": days,
        "missed_alpha_count": len(missed),
        "accepted_count": len(accepted),
        "missed_alpha": missed[:20]  # Top 20 for reference
    }
    with open("data/shadow_alpha_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info("📄 Report saved to data/shadow_alpha_report.json")

    if send_alert and missed:
        send_telegram_report(missed)

if __name__ == "__main__":
    main()

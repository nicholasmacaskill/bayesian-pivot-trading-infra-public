#!/usr/bin/env python3
"""
Performance Audit Script
Pulls raw trade data from Supabase and prints a full performance breakdown.
"""

import os, sys
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env.local'))

from supabase import create_client

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not url or not key:
    print("ERROR: Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
    sys.exit(1)

sb = create_client(url, key)

# ── 1. JOURNAL (Executed Trades) ─────────────────────────────────────────────
print("\n" + "="*60)
print("JOURNAL: ALL TRADES")
print("="*60)

resp = sb.table("journal").select("*").order("timestamp", desc=False).execute()
trades = resp.data

if not trades:
    print("No trades found in journal.")
else:
    total = len(trades)
    system_trades  = [t for t in trades if t.get("strategy", "ROGUE").upper() != "ROGUE"]
    rogue_trades   = [t for t in trades if t.get("strategy", "ROGUE").upper() == "ROGUE"]
    closed_trades  = [t for t in trades if t.get("status", "").upper() == "CLOSED"]

    def stats(lst, label):
        if not lst:
            print(f"\n{label}: No trades")
            return
        pnls = [t.get("pnl", 0) or 0 for t in lst]
        wins  = [p for p in pnls if p > 0]
        losses= [p for p in pnls if p < 0]
        win_rate = len(wins)/len(pnls)*100 if pnls else 0
        total_pnl = sum(pnls)
        avg_win   = sum(wins)/len(wins)   if wins   else 0
        avg_loss  = sum(losses)/len(losses) if losses else 0
        rr = abs(avg_win/avg_loss) if avg_loss != 0 else float('inf')
        avg_grade = sum(t.get("ai_grade",0) or 0 for t in lst)/len(lst)
        print(f"\n{label}")
        print(f"  Count      : {len(lst)}")
        print(f"  Win Rate   : {win_rate:.1f}% ({len(wins)}W / {len(losses)}L)")
        print(f"  Total PnL  : {total_pnl:+.2f}")
        print(f"  Avg Win    : {avg_win:+.2f}")
        print(f"  Avg Loss   : {avg_loss:+.2f}")
        print(f"  R:R Ratio  : {rr:.2f}:1")
        print(f"  Avg AI Grade: {avg_grade:.1f}/10")
        for t in lst[-5:]:
            dev = t.get("deviations","") or ""
            print(f"    [{t.get('timestamp','')[:10]}] {t.get('symbol','')} {t.get('side','')} | PnL: {t.get('pnl',0):+.2f} | Grade: {t.get('ai_grade',0)} | Strategy: {t.get('strategy','?')} | Deviated: {'YES' if dev else 'NO'}")

    stats(trades, "ALL TRADES")
    stats(system_trades, "SYSTEM TRADES (non-ROGUE strategy)")
    stats(rogue_trades, "ROGUE TRADES")

# ── 2. SCANS (System Calls) ──────────────────────────────────────────────────
print("\n" + "="*60)
print("SCANS: SYSTEM SIGNALS")
print("="*60)

resp2 = sb.table("scans").select("*").order("timestamp", desc=False).execute()
scans = resp2.data

if not scans:
    print("No scans found.")
else:
    total_scans = len(scans)
    verdicts = {}
    for s in scans:
        v = s.get("verdict","N/A") or "N/A"
        verdicts[v] = verdicts.get(v,0) + 1

    statuses = {}
    for s in scans:
        st = s.get("status","?") or "?"
        statuses[st] = statuses.get(st,0) + 1

    scores = [s.get("ai_score",0) or 0 for s in scans]
    avg_score = sum(scores)/len(scores) if scores else 0

    print(f"  Total Scans  : {total_scans}")
    print(f"  Avg AI Score : {avg_score:.2f}")
    print(f"  Verdicts     : {verdicts}")
    print(f"  Statuses     : {statuses}")

    # Most recent 10 scans
    print("\n  Last 10 scans:")
    for s in scans[-10:]:
        print(f"    [{s.get('timestamp','')[:10]}] {s.get('symbol','')} | {s.get('pattern','')} | bias={s.get('bias','')} | score={s.get('ai_score','')} | verdict={s.get('verdict','')} | status={s.get('status','')}")

# ── 3. SYNC STATE (Equity / Account Health) ──────────────────────────────────
print("\n" + "="*60)
print("SYNC STATE: ACCOUNT METRICS")
print("="*60)

resp3 = sb.table("sync_state").select("*").execute()
sync = resp3.data
if sync:
    for row in sync:
        print(f"  {row.get('key','')}: {row.get('value','')}  (updated: {str(row.get('last_updated',''))[:16]})")
else:
    print("  No sync state data found.")

print("\n" + "="*60)
print("AUDIT COMPLETE")
print("="*60)

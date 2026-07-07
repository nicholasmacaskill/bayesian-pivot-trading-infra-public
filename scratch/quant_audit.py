#!/usr/bin/env python3
"""
SOVEREIGN QUANT AUDITOR
=======================
Full audit pipeline:
  1. Pull ALL closed trades from TradeLocker (both accounts, last 180 days)
  2. Pull ALL scans + journal entries from Supabase
  3. Match live trades → system calls (by symbol + time window)
  4. Identify ROGUE trades (no matching scan within ±4h)
  5. Evaluate HARD_LOGIC_REJECT scans — should any have triggered?
  6. Print full performance attribution report
"""

import os, sys, json
from datetime import datetime, timedelta
from collections import defaultdict

# ── Environment ───────────────────────────────────────────────────────────────
os.chdir('/Users/nicholasmacaskill/sovereignSMC/bayesian-pivot-trading-infra')
from dotenv import load_dotenv
load_dotenv('.env.local')

sys.path.insert(0, '.')
from src.clients.tl_client import TradeLockerHelper
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

MATCH_WINDOW_HOURS = 4   # A trade is "system-called" if a scan existed within ±4h
SCORE_THRESHOLD    = 5.0 # Scans at or above this score we call "actionable"

# ── 1. PULL TRADELOCKER LEDGER (both accounts, 180-day window) ────────────────
print("\n" + "="*65)
print("STEP 1: FETCHING TRADELOCKER LEDGER")
print("="*65)

accounts_cfg = [
    dict(
        label="Account A",
        email=os.environ.get("TRADELOCKER_EMAIL"),
        password=os.environ.get("TRADELOCKER_PASSWORD"),
        server=os.environ.get("TRADELOCKER_SERVER", "UPCOMS"),
        base_url=os.environ.get("TRADELOCKER_BASE_URL", "https://demo.tradelocker.com"),
    ),
    dict(
        label="Account B",
        email=os.environ.get("TRADELOCKER_EMAIL_B"),
        password=os.environ.get("TRADELOCKER_PASSWORD_B"),
        server=os.environ.get("TRADELOCKER_SERVER_B", "UPCOMS"),
        base_url=os.environ.get("TRADELOCKER_BASE_URL_B", "https://demo.tradelocker.com"),
    ),
]

all_tl_trades = []
for cfg in accounts_cfg:
    if not cfg["email"] or not cfg["password"]:
        print(f"  [{cfg['label']}] No credentials — skipping")
        continue
    helper = TradeLockerHelper(cfg["email"], cfg["password"], cfg["server"], cfg["base_url"])
    ok = helper.login()
    if not ok:
        print(f"  [{cfg['label']}] Login FAILED")
        continue
    print(f"  [{cfg['label']}] Logged in — account_id={helper.account_id}, acc_num={helper.acc_num}")
    # Pull wide window: 180 days
    trades = helper.get_recent_history(hours=180*24)
    for t in trades:
        t["_account"] = cfg["label"]
    print(f"  [{cfg['label']}] {len(trades)} closed trades fetched")
    all_tl_trades.extend(trades)

print(f"\n  TOTAL TL CLOSED TRADES: {len(all_tl_trades)}")

# Parse close_time → datetime for all TL trades
for t in all_tl_trades:
    try:
        t["_dt"] = datetime.fromisoformat(t.get("close_time","").replace("Z",""))
    except:
        t["_dt"] = datetime.min

# ── 2. PULL SUPABASE DATA ─────────────────────────────────────────────────────
print("\n" + "="*65)
print("STEP 2: FETCHING SUPABASE SCANS + JOURNAL")
print("="*65)

# Scans - all
scans_resp = sb.table("scans").select("*").order("timestamp", desc=False).execute()
scans = scans_resp.data or []
print(f"  Scans total: {len(scans)}")

# Journal - all
journal_resp = sb.table("journal").select("*").order("timestamp", desc=False).execute()
journal = journal_resp.data or []
print(f"  Journal entries total: {len(journal)}")

# Parse datetimes
for s in scans:
    try:
        s["_dt"] = datetime.fromisoformat(s["timestamp"].replace("Z","").split("+")[0])
    except:
        s["_dt"] = datetime.min

for j in journal:
    try:
        j["_dt"] = datetime.fromisoformat(j["timestamp"].replace("Z","").split("+")[0])
    except:
        j["_dt"] = datetime.min

# Real scans only (not heartbeats, not TEST)
real_scans = [s for s in scans if s.get("verdict") not in ("SCAN_HEARTBEAT", "TEST", None) or s.get("ai_score", 0) > 0]
actionable_scans = [s for s in scans if (s.get("ai_score") or 0) >= SCORE_THRESHOLD]

print(f"  Real scans (non-heartbeat): {len(real_scans)}")
print(f"  Actionable scans (score≥{SCORE_THRESHOLD}): {len(actionable_scans)}")

# Normalize symbol for matching
def norm_sym(s):
    if not s: return ""
    return s.upper().replace(" ", "").split("(")[0].strip()

# ── 3. MATCH TL TRADES → SYSTEM CALLS ────────────────────────────────────────
print("\n" + "="*65)
print("STEP 3: MATCHING TL TRADES → SYSTEM SCANS")
print("="*65)

def find_matching_scan(trade, scans, window_hours=MATCH_WINDOW_HOURS):
    """Find best scan match for a trade by symbol + time window."""
    trade_sym  = norm_sym(trade.get("symbol",""))
    trade_time = trade["_dt"]
    best       = None
    best_score = -1
    for s in scans:
        scan_sym = norm_sym(s.get("symbol",""))
        # Symbol must match (partial OK: BTC matches BTC/USD)
        if trade_sym[:3] not in scan_sym and scan_sym[:3] not in trade_sym:
            continue
        delta_h = abs((trade_time - s["_dt"]).total_seconds()) / 3600
        if delta_h <= window_hours:
            score = s.get("ai_score") or 0
            if score > best_score:
                best_score = score
                best = s
    return best

matched   = []  # (tl_trade, scan)
unmatched = []  # tl_trade with no scan

for t in all_tl_trades:
    scan = find_matching_scan(t, real_scans)
    if scan:
        matched.append((t, scan))
    else:
        unmatched.append(t)

print(f"  TL trades matched to a system scan : {len(matched)}")
print(f"  TL trades with NO matching scan    : {len(unmatched)}  ← likely ROGUE")

# ── 4. PERFORMANCE ATTRIBUTION ────────────────────────────────────────────────
print("\n" + "="*65)
print("STEP 4: PERFORMANCE ATTRIBUTION")
print("="*65)

def pnl_stats(trades, label):
    if not trades:
        print(f"\n{label}: No trades")
        return {}
    pnls  = [t.get("pnl", 0) or 0 for t in trades]
    wins  = [p for p in pnls if p > 0]
    loss  = [p for p in pnls if p < 0]
    total = sum(pnls)
    wr    = len(wins)/len(pnls)*100 if pnls else 0
    aw    = sum(wins)/len(wins)     if wins  else 0
    al    = sum(loss)/len(loss)     if loss  else 0
    rr    = abs(aw/al)              if al    else float("inf")
    print(f"\n{'─'*50}")
    print(f"  {label}")
    print(f"  Trades   : {len(pnls)}")
    print(f"  Win Rate : {wr:.1f}%  ({len(wins)}W / {len(loss)}L)")
    print(f"  Total PnL: ${total:+,.2f}")
    print(f"  Avg Win  : ${aw:+,.2f}   Avg Loss: ${al:+,.2f}")
    print(f"  R:R      : {rr:.2f}:1")
    return {"count": len(pnls), "wr": wr, "total_pnl": total, "rr": rr}

matched_trades   = [t for t,_ in matched]
unmatched_trades = unmatched

sys_stats   = pnl_stats(matched_trades,   "SYSTEM-MATCHED TRADES (had a scan within ±4h)")
rogue_stats = pnl_stats(unmatched_trades, "ROGUE TRADES (no system scan found)")

# Biggest rogue losers
print("\n  TOP 10 ROGUE LOSSES:")
rogue_sorted = sorted(unmatched_trades, key=lambda t: t.get("pnl", 0))
for t in rogue_sorted[:10]:
    print(f"    [{str(t.get('close_time',''))[:16]}] {t.get('symbol','')} {t.get('side','')} | PnL: ${t.get('pnl',0):+,.2f} | acct: {t.get('_account','')}")

# Best system-matched winners
print("\n  TOP 10 SYSTEM-MATCHED WINNERS:")
matched_sorted = sorted(matched_trades, key=lambda t: t.get("pnl", 0), reverse=True)
for t in matched_sorted[:10]:
    print(f"    [{str(t.get('close_time',''))[:16]}] {t.get('symbol','')} {t.get('side','')} | PnL: ${t.get('pnl',0):+,.2f} | acct: {t.get('_account','')}")

# ── 5. EVALUATE HARD_LOGIC_REJECT SCANS ──────────────────────────────────────
print("\n" + "="*65)
print("STEP 5: SHOULD-HAVE-FIRED SCAN ANALYSIS")
print("="*65)
print("  (Evaluating HARD_LOGIC_REJECT scans with score ≥ 5 — did price move in their direction?)")

try:
    import yfinance as yf
    import pandas as pd

    rejected = [s for s in scans if s.get("verdict") == "HARD_LOGIC_REJECT" and (s.get("ai_score") or 0) >= SCORE_THRESHOLD]
    print(f"  High-score rejected scans to evaluate: {len(rejected)}")

    symbol_map = {"BTC/USD": "BTC-USD", "ETH/USD": "ETH-USD", "SOL/USD": "SOL-USD"}
    data_cache = {}
    symbols_needed = set(s["symbol"] for s in rejected if s["symbol"] in symbol_map)
    for sym in symbols_needed:
        yf_sym = symbol_map[sym]
        print(f"  Downloading 1h data for {sym}...")
        df = yf.download(yf_sym, start=(datetime.utcnow()-timedelta(days=90)).strftime('%Y-%m-%d'), interval="1h", progress=False)
        if not df.empty:
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            if df.index.tz is not None: df.index = df.index.tz_localize(None)
            data_cache[sym] = df

    would_have_won  = []
    would_have_lost = []
    no_data         = []

    for s in rejected:
        sym = s.get("symbol","")
        if sym not in data_cache:
            no_data.append(s)
            continue

        df = data_cache[sym]
        sig_time  = s["_dt"]
        bias      = (s.get("bias") or "").upper()
        direction = "LONG" if "BULL" in bias or "LONG" in bias else ("SHORT" if "BEAR" in bias or "SHORT" in bias else None)
        if not direction:
            # Try pattern field
            pat = (s.get("pattern") or "").lower()
            direction = "LONG" if "bullish" in pat else ("SHORT" if "bearish" in pat else None)
        if not direction:
            no_data.append(s)
            continue

        after = df[df.index >= sig_time].head(48)  # 48h window
        if after.empty:
            no_data.append(s)
            continue

        try:
            entry = float(after.iloc[0]["Open"])
            high  = float(after["High"].max())
            low   = float(after["Low"].min())
        except:
            no_data.append(s)
            continue

        # Rough 2.5R target vs 1R SL estimate using 0.5% risk
        risk = entry * 0.005
        if direction == "LONG":
            moved_in_favor = (high - entry) / risk  # R achieved
        else:
            moved_in_favor = (entry - low)  / risk

        s["_direction"]    = direction
        s["_r_achieved"]   = round(moved_in_favor, 2)
        s["_entry_est"]    = round(entry, 2)

        if moved_in_favor >= 2.5:
            would_have_won.append(s)
        elif moved_in_favor < 0:
            would_have_lost.append(s)
        else:
            # Partial move — inconclusive
            pass

    print(f"\n  HARD_LOGIC_REJECT scans that would have hit 2.5R+ TP : {len(would_have_won)}")
    print(f"  HARD_LOGIC_REJECT scans that moved against direction  : {len(would_have_lost)}")
    print(f"  Insufficient data / no direction inferred            : {len(no_data)}")

    if would_have_won:
        print(f"\n  ⚠️  MISSED WINNERS (filter too tight):")
        for s in sorted(would_have_won, key=lambda x: x.get("_r_achieved", 0), reverse=True)[:10]:
            print(f"    [{str(s.get('timestamp',''))[:16]}] {s.get('symbol','')} {s['_direction']} | score={s.get('ai_score')} | R_achieved={s['_r_achieved']} | pattern={s.get('pattern','')}")

    if would_have_lost:
        print(f"\n  ✅  CORRECT REJECTS (filter saved you):")
        for s in sorted(would_have_lost, key=lambda x: x.get("_r_achieved", 0))[:5]:
            print(f"    [{str(s.get('timestamp',''))[:16]}] {s.get('symbol','')} {s['_direction']} | score={s.get('ai_score')} | pattern={s.get('pattern','')}")

except ImportError:
    print("  yfinance not available — skipping price simulation")
except Exception as e:
    print(f"  Price simulation error: {e}")

# ── 6. FINAL VERDICT ──────────────────────────────────────────────────────────
print("\n" + "="*65)
print("STEP 6: QUANT VERDICT")
print("="*65)

total_tl = len(all_tl_trades)
total_pnl_all = sum(t.get("pnl", 0) or 0 for t in all_tl_trades)
rogue_pnl     = sum(t.get("pnl", 0) or 0 for t in unmatched_trades)
sys_pnl       = sum(t.get("pnl", 0) or 0 for t in matched_trades)

print(f"\n  Total TL closed trades   : {total_tl}")
print(f"  Total net PnL (all)      : ${total_pnl_all:+,.2f}")
print(f"  System-matched PnL       : ${sys_pnl:+,.2f}")
print(f"  Rogue trade PnL          : ${rogue_pnl:+,.2f}  ← the tax you paid")
rogue_pct = (abs(rogue_pnl) / max(abs(total_pnl_all), 1)) * 100 if total_tl else 0
print(f"\n  Rogue trades represent   : {len(unmatched_trades)}/{total_tl} trades ({len(unmatched_trades)/max(total_tl,1)*100:.0f}% of volume)")
print(f"  Rogue PnL as % of total  : {rogue_pct:.0f}%")

if rogue_pnl < -100:
    print(f"\n  🔴 VERDICT: Rogue trading is a net drag. Eliminating it would add ${abs(rogue_pnl):,.2f} to your bottom line.")
elif sys_pnl > 0 and rogue_pnl < 0:
    print(f"\n  🟡 VERDICT: System has positive edge, rogue trades are eroding it.")
elif sys_pnl <= 0 and rogue_pnl <= 0:
    print(f"\n  ⚫ VERDICT: Both system and rogue trades are losing. System calibration needed.")
else:
    print(f"\n  🟢 VERDICT: Surprisingly, rogue trades are net positive — but check sample size.")

print("\n" + "="*65)
print("AUDIT COMPLETE")
print("="*65 + "\n")

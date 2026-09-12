"""
Payout Analysis Script — All Active Accounts
Pulls live balances + full trade history, computes consistency metrics,
and estimates realistic time-to-payout per Upcomers rules.
"""
import sys, os
sys.path.append(os.getcwd())

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from src.clients.tl_client import TradeLockerClient

# ── Upcomers Funded Payout Targets ──────────────────────────────────────────
TIER_TARGETS = {
    10000.0: {"target": 11000.0, "daily_cap_pct": 0.20},  # $1,000 profit goal
    25000.0: {"target": 27000.0, "daily_cap_pct": 0.20},  # $2,000 profit goal
    50000.0: {"target": 55000.0, "daily_cap_pct": 0.20},  # $5,000 profit goal
}
FROZEN = {"h4sj53tg4f@upcomers.com", "hnr10rtj4k@upcomers.com", "vkrbpwdprh@upcomers.com"}

def get_tier(balance: float) -> float:
    if balance >= 40000:   return 50000.0
    elif balance >= 18000: return 25000.0
    else:                  return 10000.0

def trading_days_from_now(days: int) -> str:
    cur = datetime.now(timezone.utc)
    added = 0
    while added < max(1, days):
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            added += 1
    return cur.strftime("%b %d, %Y")

def analyze_account(h, idx: int):
    print(f"\n{'='*72}")
    email_short = h.email.split("@")[0]

    h.login()
    h.get_account_details()
    balance   = getattr(h, 'balance', 0.0)
    status    = getattr(h, 'account_status', 'UNKNOWN')
    tier      = get_tier(balance)
    cfg       = TIER_TARGETS.get(tier, TIER_TARGETS[25000.0])
    target    = cfg["target"]
    profit_target = target - tier                  # e.g. $2,000 on a $25k
    daily_cap = profit_target * cfg["daily_cap_pct"]  # e.g. $400/day max

    # Live floating PnL
    open_pos = h.get_open_positions()
    floating = sum(float(p.get('pnl', 0.0)) for p in open_pos)
    equity   = balance + floating

    # Current profit relative to initial tier (not HWM — payout is from starting balance)
    current_profit = balance - tier  # can be negative
    profit_needed  = max(0.0, target - balance)

    frozen = h.email in FROZEN

    print(f"Account {idx}: {email_short}@upcomers  |  Tier: ${tier:,.0f}  |  Status: {status}{'  🔴 FROZEN' if frozen else ''}")
    print(f"  Balance: ${balance:,.2f}  |  Floating: ${floating:+.2f}  |  Equity: ${equity:,.2f}")
    print(f"  Payout Target: ${target:,.0f}  |  Total Profit Goal: ${profit_target:,.0f}")
    print(f"  Profit So Far: ${current_profit:+,.2f}  ({100*current_profit/profit_target:.1f}% of goal)")
    print(f"  Still Needed:  ${profit_needed:,.2f}")
    print(f"  20% Daily Cap: ${daily_cap:,.0f}/day max")

    if frozen:
        print(f"\n  ⛔ ACCOUNT FROZEN — No new trades permitted. Must recover manually or reset.")
        return

    # ── Pull full trade history (30 days) ───────────────────────────────────
    raw_trades = h.get_recent_history(hours=720)  # 30 days

    # Group trades by calendar date (UTC date of close)
    by_day = defaultdict(list)
    for t in raw_trades:
        ts = t.get('time_ms') or t.get('close_time_ms') or 0
        if ts:
            day = datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d")
        else:
            day = "unknown"
        by_day[day].append(t)

    # Per-day PnL
    day_pnls = {}
    for day, trades in by_day.items():
        if day == "unknown":
            continue
        day_pnls[day] = sum(float(t.get('pnl', 0.0)) for t in trades)

    total_trades   = len(raw_trades)
    wins           = [t for t in raw_trades if float(t.get('pnl', 0.0)) > 0]
    losses         = [t for t in raw_trades if float(t.get('pnl', 0.0)) <= 0]
    win_rate       = len(wins) / total_trades * 100 if total_trades else 0
    avg_win        = sum(float(t.get('pnl', 0.0)) for t in wins) / len(wins) if wins else 0
    avg_loss       = sum(float(t.get('pnl', 0.0)) for t in losses) / len(losses) if losses else 0
    expectancy     = (win_rate/100 * avg_win) + ((1 - win_rate/100) * avg_loss)

    print(f"\n  ── 30-Day Trade History ──")
    print(f"  Total Trades: {total_trades}  |  Wins: {len(wins)}  |  Losses: {len(losses)}  |  Win Rate: {win_rate:.1f}%")
    print(f"  Avg Win: ${avg_win:+.2f}  |  Avg Loss: ${avg_loss:+.2f}  |  Expectancy/Trade: ${expectancy:+.2f}")

    # Consistency check — largest single day vs daily cap
    if day_pnls:
        best_day_key   = max(day_pnls, key=day_pnls.get)
        best_day_pnl   = day_pnls[best_day_key]
        worst_day_key  = min(day_pnls, key=day_pnls.get)
        worst_day_pnl  = day_pnls[worst_day_key]
        active_days    = len([d for d in day_pnls.values() if d != 0])
        avg_daily_pnl  = sum(day_pnls.values()) / active_days if active_days else 0
        days_above_cap = [d for d, pnl in day_pnls.items() if pnl > daily_cap]

        print(f"\n  ── Consistency Audit ──")
        print(f"  Active Trading Days (30d): {active_days}")
        print(f"  Best Day:  {best_day_key} → ${best_day_pnl:+.2f}  {'⚠️  OVER CAP' if best_day_pnl > daily_cap else '✅'}")
        print(f"  Worst Day: {worst_day_key} → ${worst_day_pnl:+.2f}")
        print(f"  Avg Daily PnL: ${avg_daily_pnl:+.2f}")
        if days_above_cap:
            print(f"  ⚠️  Days Over 20% Cap ({len(days_above_cap)}): {', '.join(days_above_cap)}")
            print(f"     → These days may need to be explained to Upcomers at payout.")
        else:
            print(f"  ✅ No days exceed the 20% consistency cap — clean payout history.")
    else:
        avg_daily_pnl = expectancy * 0.5  # fallback: assume ~0.5 trades/day
        print(f"  No closed trade history found in last 30 days.")

    # ── Time-to-Payout Estimates ─────────────────────────────────────────────
    print(f"\n  ── Time to Payout ──")
    if profit_needed <= 0:
        print(f"  🎯 PAYOUT READY — Balance ${balance:,.2f} already exceeds target ${target:,.0f}!")
        print(f"     Request payout immediately.")
        return

    # Use actual avg daily PnL if positive, else fallback to system expectancy
    realistic_daily = avg_daily_pnl if day_pnls and avg_daily_pnl > 0 else max(expectancy * 0.5, 1.0)

    # Scenarios
    scenarios = [
        ("Fastest (20% cap/day)", daily_cap),
        ("Historical Avg Daily", realistic_daily),
        ("Conservative (50% of hist avg)", max(realistic_daily * 0.5, 1.0)),
    ]

    for label, daily_rate in scenarios:
        if daily_rate <= 0:
            print(f"  {label}: ∞ (negative expectancy — requires strategy fix)")
            continue
        days_needed = int(-(-profit_needed // daily_rate))  # ceiling division
        eta = trading_days_from_now(days_needed)
        print(f"  {label}: ${daily_rate:.0f}/day → ~{days_needed} trading days → ETA: {eta}")


def main():
    print("SOVEREIGN SMC — PAYOUT READINESS ANALYSIS")
    print(f"Run Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    tl = TradeLockerClient()
    for i, h in enumerate(tl.helpers, 1):
        try:
            analyze_account(h, i)
        except Exception as e:
            print(f"\nAccount {i} ERROR: {e}")
        import time
        time.sleep(2.5)  # Rate limit pacing between accounts

    print(f"\n{'='*72}")
    print("Analysis complete.")

if __name__ == "__main__":
    main()

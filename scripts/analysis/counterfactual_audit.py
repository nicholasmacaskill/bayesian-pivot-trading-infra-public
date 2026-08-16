import sys
import os
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.engines.counterfactual_tracker import CounterfactualTracker
from src.core.database import get_db_connection

def run_audit():
    print("=" * 75)
    print(" 👻 BAYESIAN PIVOT — COUNTERFACTUAL AGENT PERFORMANCE AUDIT")
    print("=" * 75)

    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM counterfactual_trades ORDER BY id DESC").fetchall()
    conn.close()

    if not rows:
        print("\nℹ️ No counterfactual shadow trades recorded yet.")
        print("  Shadow trades will populate as candidate setups hit per-account filters.\n")
        return

    print(f"\n📊 Total Logged Shadow Setups: {len(rows)}\n")
    print(f"{'ID':<5} | {'Account':<11} | {'Symbol':<8} | {'Side':<4} | {'Outcome':<8} | {'Sim PnL':<10} | {'Rejection Filters'}")
    print("-" * 75)

    for row in rows[:20]: # Show latest 20
        r = dict(row)
        reasons = json.loads(r["rejection_reasons"] or "[]")
        clean_reasons = ", ".join([rs.split("(")[0].strip() for rs in reasons])
        pnl_str = f"${float(r['simulated_pnl'] or 0):>+7.2f}"
        print(f"{r['id']:<5} | {r['account_key']:<11} | {r['symbol']:<8} | {r['direction']:<4} | {r['outcome']:<8} | {pnl_str:<10} | {clean_reasons}")

    print("\n" + "=" * 75)
    print(" 📈 AGGREGATED FILTER EFFICIENCY METRICS")
    print("=" * 75)

    summary = CounterfactualTracker.get_counterfactual_summary()
    by_account = summary.get("by_account", {})
    by_filter = summary.get("by_filter", {})

    print("\n--- PERFORMANCE BY ACCOUNT PROFILE ---")
    for acc, stats in by_account.items():
        total = stats["total"]
        hits_tp = stats["hits_tp"]
        hits_sl = stats["hits_sl"]
        net_pnl = stats["net_pnl"]
        wr = (hits_tp / total * 100) if total > 0 else 0
        print(f" • {acc:<11}: Setups={total:<3} | Hits TP={hits_tp:<3} | Hits SL={hits_sl:<3} | WinRate={wr:>5.1f}% | Net Shadow PnL=${net_pnl:>+8.2f}")

    print("\n--- PERFORMANCE IMPACT BY FILTER CATEGORY ---")
    for flt, stats in by_filter.items():
        total = stats["total"]
        hits_tp = stats["hits_tp"]
        hits_sl = stats["hits_sl"]
        net_pnl = stats["net_pnl"]
        print(f" • {flt:<25}: Blocked={total:<3} | Missed Wins={hits_tp:<3} | Prevented Losses={hits_sl:<3} | Net Impact=${net_pnl:>+8.2f}")

    print("=" * 75 + "\n")

if __name__ == "__main__":
    run_audit()

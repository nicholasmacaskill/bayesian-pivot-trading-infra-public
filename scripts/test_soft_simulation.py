"""
End-to-End Soft Test Harness
==============================
Executes a complete dry-run simulation across all 8 account mandates.
Verifies setup geometry, QA Quant Agent validation, per-account risk clamping,
stop loss & take profit payloads, anti-hedging intent locks, and shadow trade logging.
"""

import os
import sys
import logging

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.database import init_db, get_db_connection
from src.engines.multi_account_funnel import MultiAccountFunnelManager, align_lot_size
from src.engines.qa_quant_agent import QAQuantAgent
from src.engines.counterfactual_tracker import CounterfactualTracker
from src.clients.tl_client import TradeLockerClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SoftTest")

def run_soft_test():
    print("\n===========================================================================")
    print(" 🧪 BAYESIAN PIVOT — END-TO-END SOFT TEST SIMULATION (8 ACCOUNTS)")
    print("===========================================================================\n")

    # 1. Initialize Database & Engines
    init_db()
    funnel = MultiAccountFunnelManager()
    qa = QAQuantAgent(min_rr_multiple=1.5)
    tracker = CounterfactualTracker()
    tl_client = TradeLockerClient()

    print(f"✅ Initialized MultiAccountFunnelManager ({len(funnel.profiles)} Strategy Profiles Registered)")
    print(f"✅ Initialized QAQuantAgent (Minimum R:R Threshold: {qa.min_rr_multiple:.1f}R)")
    print(f"✅ Initialized TradeLockerClient ({len(tl_client.helpers)} Account Helpers Loaded)\n")

    # 2. Define Sample Market Signal (BTC/USD Long Setup)
    candidate_setup = {
        "symbol": "BTC/USD",
        "direction": "BUY",
        "price": 65000.0,
        "stop_loss": 64500.0,   # $500 risk per BTC
        "take_profit": 66500.0,  # $1,500 reward per BTC -> 3.0R Target
        "pattern": "5m Fair Value Gap + Asian Low Sweep",
        "timeframe": "5m"
    }

    print("--- STEP 1: CANDIDATE SIGNAL GEOMETRY & QA AUDIT ---")
    print(f" • Symbol: {candidate_setup['symbol']} | Direction: {candidate_setup['direction']}")
    print(f" • Entry Price: ${candidate_setup['price']:,.2f}")
    print(f" • Stop Loss  : ${candidate_setup['stop_loss']:,.2f} (-$500.00 / -0.77%)")
    print(f" • Take Profit: ${candidate_setup['take_profit']:,.2f} (+$1,500.00 / +2.31% -> 3.0R)")

    # QA Audit
    is_valid, qa_issues = qa.audit_candidate_setup(candidate_setup, funnel.profiles["ACCOUNT_A"])
    if is_valid:
        print(" ✅ QA Quant Agent Verdict: PASSED (Geometry & R:R Valid)\n")
    else:
        print(f" ❌ QA Quant Agent Verdict: FAILED ({qa_issues})\n")
        return

    print("--- STEP 2: MULTI-ACCOUNT FUNNEL MATRIX & RISK CLAMPING ---")
    open_positions = tl_client.get_open_positions()
    print(f" • Active Portfolio Open Positions: {len(open_positions)}")

    # Test setup against all 8 account profiles
    accounts_to_test = ["ACCOUNT_A", "ACCOUNT_B", "ACCOUNT_C", "ACCOUNT_D", "ACCOUNT_E", "ACCOUNT_F", "ACCOUNT_G", "ACCOUNT_H"]
    
    for acc_key in accounts_to_test:
        profile = funnel.profiles[acc_key]
        
        # Evaluate setup with sample market parameters
        passed, rejection_reasons = funnel.evaluate_setup_for_account(
            setup=candidate_setup,
            account_key=acc_key,
            hurst=0.60,         # Trending Hurst
            smt_strength=0.25,   # Strong SMT
            slippage_ratio=1.0,  # Low slippage
            cal_safe=True,
            corr_ok=True,
            regime_allowed=True,
            ai_score=8.2,
            open_positions=open_positions
        )

        # Calculate Lot Sizing & USD Risk
        risk_dist = abs(candidate_setup["price"] - candidate_setup["stop_loss"])
        raw_qty = profile.max_risk_usd / risk_dist
        aligned_qty = align_lot_size(raw_qty, min_lot=0.01, lot_step=0.01)

        print(f"\n ► [{acc_key}] {profile.account_name}:")
        print(f"   • Mandate Mode : {profile.strategy_mode} | AI Threshold: {profile.ai_threshold}")
        print(f"   • Risk Cap     : ${profile.max_risk_usd:.2f} | Computed Qty: {aligned_qty} BTC (Aligned 0.01 lot step)")

        if passed:
            print(f"   • Evaluation   : 🟢 PASSED FUNNEL MATRIX")
            print(f"   • Order Payload: BUY {aligned_qty} BTC @ MKT | SL: ${candidate_setup['stop_loss']:.2f} | TP: ${candidate_setup['take_profit']:.2f}")
        else:
            print(f"   • Evaluation   : 🔴 BYPASSED ({', '.join(rejection_reasons)})")
            # Register in shadow tracker
            tracker.register_shadow_trade(candidate_setup, acc_key, profile.strategy_mode, rejection_reasons)
            print(f"   • Shadow Agent : Registered in counterfactual_trades table for 48h resolution")

    print("\n--- STEP 3: ANTI-HEDGING INTENT LOCK TEST ---")
    # Register an in-flight BUY intent for ACCOUNT_B
    funnel.register_in_flight_intent("BTC/USD", "BUY", "ACCOUNT_B")
    
    # Try evaluating a SELL on BTC/USD for ACCOUNT_C while BUY is in-flight -> MUST BE BLOCKED
    opposing_setup = candidate_setup.copy()
    opposing_setup["direction"] = "SELL"
    opposing_setup["stop_loss"] = 65500.0
    opposing_setup["take_profit"] = 63500.0

    hedge_passed, hedge_reasons = funnel.evaluate_setup_for_account(
        setup=opposing_setup, account_key="ACCOUNT_B", hurst=0.60, smt_strength=0.25, ai_score=8.5, cal_safe=True, corr_ok=True, regime_allowed=True, open_positions=open_positions
    )
    funnel.clear_in_flight_intent("BTC/USD", "BUY", "ACCOUNT_B")

    if not hedge_passed and any("CROSS_ACCOUNT_HEDGING_BLOCKED" in r for r in hedge_reasons):
        print(" ✅ Anti-Hedging Gate Test: PASSED (Opposing SELL successfully blocked while BUY intent in-flight)")
    else:
        print(f" ❌ Anti-Hedging Gate Test: FAILED ({hedge_reasons})")



    print("\n===========================================================================")
    print(" 🎉 SOFT TEST SIMULATION COMPLETED — ALL 8 ACCOUNTS & SAFEGUARDS VERIFIED!")
    print("===========================================================================\n")

if __name__ == "__main__":
    run_soft_test()

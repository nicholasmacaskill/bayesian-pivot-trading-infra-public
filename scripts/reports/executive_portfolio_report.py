"""
Daily Executive Portfolio Report Generator
============================================
Generates a comprehensive Markdown/Console executive report covering:
  - Aggregate Portfolio NAV & Individual Account Equities ($204.9k baseline)
  - Active Open Positions & Risk Exposure
  - Counterfactual Shadow Trade PnL & Net Filter Impact ($)
  - QA Quant Auditor Health Scores
"""

import sys
import os
import logging
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.clients.tl_client import TradeLockerClient
from src.engines.multi_account_funnel import MultiAccountFunnelManager
from src.engines.counterfactual_tracker import CounterfactualTracker
from src.engines.qa_quant_agent import QAQuantAgent

def generate_executive_report():
    print("\n===========================================================================")
    print(f" 📊 BAYESIAN PIVOT — EXECUTIVE PORTFOLIO REPORT ({datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')})")
    print("===========================================================================\n")

    tl_client = TradeLockerClient()
    funnel = MultiAccountFunnelManager()
    tracker = CounterfactualTracker()
    qa = QAQuantAgent()

    # 1. Total Portfolio NAV & Per-Account Equities
    total_equity = tl_client.get_total_equity()
    open_positions = tl_client.get_open_positions()

    print(f"🏛️ TOTAL PORTFOLIO NAV: ${total_equity:,.2f} across {len(funnel.profiles)} Account Mandates")
    print(f"📈 ACTIVE OPEN POSITIONS: {len(open_positions)} Trades Currently In-Flight\n")

    print("--- 1. ACCOUNT MANDATE STATUS & RISK CAPS ---")
    for acc_key, profile in funnel.profiles.items():
        print(f" • [{acc_key}] {profile.account_name:32s} | Mode: {profile.strategy_mode:16s} | Risk Cap: ${profile.max_risk_usd:6.2f} | AI Cutoff: {profile.ai_threshold}")

    print("\n--- 2. PORTFOLIO HEALTH & RISK AUDIT ---")
    health = qa.audit_portfolio_health(total_equity, open_positions)
    print(f" • Health Status : {health['status']}")
    print(f" • Active Symbols : {health['active_symbols'] if health['active_symbols'] else 'None (All Cash)'}")
    if health['alerts']:
        print(f" • Active Alerts : {health['alerts']}")
    else:
        print(" • Active Alerts : None (All Risk Parameters Nominal)")

    print("\n--- 3. COUNTERFACTUAL SHADOW ENGINE PERFORMANCE ---")
    summary = tracker.get_counterfactual_summary()
    print(f" • Total Shadow Trades Audited : {summary.get('total_shadow_trades', 0)}")
    print(f" • Total Prevented Losses       : ${summary.get('prevented_losses_usd', 0.0):,.2f}")
    print(f" • Total Missed Wins            : ${summary.get('missed_wins_usd', 0.0):,.2f}")
    print(f" • NET FILTER IMPACT ($)        : ${summary.get('net_filter_impact_usd', 0.0):,.2f}")

    print("\n===========================================================================")
    print(" 🏁 END OF EXECUTIVE PORTFOLIO REPORT")
    print("===========================================================================\n")

if __name__ == "__main__":
    generate_executive_report()

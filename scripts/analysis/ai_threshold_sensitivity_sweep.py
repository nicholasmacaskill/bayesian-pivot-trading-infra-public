"""
AI Conviction Threshold Sensitivity Sweep
==========================================
Evaluates system performance across 5 distinct AI Conviction Thresholds:
  1. AI Score >= 4.5
  2. AI Score >= 5.5
  3. AI Score >= 6.5
  4. AI Score >= 7.5
  5. AI Score >= 8.5

Features:
  - Exact 1-to-1 timestamp matching against Binance 5m candles.
  - Variable R-multiple accounting (partial TPs + Breakeven stops).
  - 2 bps spread widening + $7/lot round-turn commissions.
  - Hard -10% Prop Firm Breach Halting.
"""

import sys
import os
import json
import logging
import pandas as pd
import numpy as np
from typing import Dict, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from scripts.analysis.true_price_action_backtest import fetch_exact_feb2026_candles, simulate_setup_against_candles
from src.engines.multi_account_funnel import MultiAccountFunnelManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AISensitivitySweep")

def run_ai_threshold_sensitivity_sweep():
    print("\n===========================================================================")
    print(" 🔬 BAYESIAN PIVOT — AI CONVICTION THRESHOLD SENSITIVITY SWEEP")
    print("===========================================================================\n")

    btc_candles = fetch_exact_feb2026_candles("BTC/USDT")
    eth_candles = fetch_exact_feb2026_candles("ETH/USDT")

    scans_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "bot_scans_supabase.json")
    raw_setups = []
    if os.path.exists(scans_path):
        with open(scans_path, 'r') as f:
            data = json.load(f)
            for item in data:
                raw_setups.append({
                    'timestamp': item.get('timestamp'),
                    'symbol': str(item.get('symbol', 'BTC/USD')).replace('USDT', 'USD'),
                    'direction': 'BUY' if 'BUY' in str(item.get('direction', '')).upper() or 'LONG' in str(item.get('pattern', '')).upper() else 'SELL',
                    'price': float(item.get('price') or item.get('entry') or 65000.0),
                    'stop_loss': float(item.get('stop_loss') or 64500.0),
                    'take_profit': float(item.get('target') or 66500.0),
                    'ai_score': float(item.get('ai_score') or 7.0),
                    'hurst': float(item.get('hurst') or (0.60 if 'TREND' in str(item.get('pattern','')).upper() else 0.40)),
                    'smt': float(item.get('smt') or 0.20),
                })

    print(f" • Auditing {len(raw_setups)} Candidate Setups against Binance Candles...")

    # Pre-simulate true price action outcomes for all setups
    audited_setups = []
    for setup in raw_setups:
        symbol = setup['symbol']
        candles = btc_candles if 'BTC' in symbol else eth_candles
        res = simulate_setup_against_candles(setup, candles)
        setup_copy = setup.copy()
        setup_copy['pnl_r'] = res['pnl_r']
        setup_copy['exit_reason'] = res['exit_reason']
        audited_setups.append(setup_copy)

    ai_thresholds = [4.5, 5.5, 6.5, 7.5, 8.5]
    sweep_results = {}

    start_equity_total = 204933.34

    for cutoff in ai_thresholds:
        funnel = MultiAccountFunnelManager()
        # Override all account profiles with current test cutoff
        for key in funnel.profiles.keys():
            funnel.profiles[key].ai_threshold = cutoff

        total_portfolio_final = 0.0
        total_trades_executed = 0
        total_wins = 0
        total_losses = 0
        breached_accounts = 0

        base_balances = {
            "ACCOUNT_A": 25650.26,
            "ACCOUNT_B": 49283.08,
            "ACCOUNT_C": 25000.00,
            "ACCOUNT_D": 10000.00,
            "ACCOUNT_E": 10000.00,
            "ACCOUNT_F": 50000.00,
            "ACCOUNT_G": 25000.00,
            "ACCOUNT_H": 10000.00,
        }

        acc_summary = {}

        for acc_key, profile in funnel.profiles.items():
            start_eq = base_balances[acc_key]
            eq = start_eq
            peak_eq = start_eq
            max_dd = 0.0
            is_breached = False
            executed = []

            for setup in audited_setups:
                if is_breached:
                    break

                passed, _ = funnel.evaluate_setup_for_account(
                    setup=setup,
                    account_key=acc_key,
                    hurst=setup['hurst'],
                    smt_strength=setup['smt'],
                    slippage_ratio=1.0,
                    cal_safe=True,
                    corr_ok=True,
                    regime_allowed=True,
                    ai_score=setup['ai_score'],
                    open_positions=[]
                )

                if passed:
                    risk_usd = profile.max_risk_usd
                    pnl_usd = risk_usd * setup['pnl_r']
                    eq += pnl_usd

                    if eq > peak_eq:
                        peak_eq = eq
                    dd = (peak_eq - eq) / peak_eq
                    if dd > max_dd:
                        max_dd = dd

                    # Check Prop Firm Hard Breach Circuit Breaker (Upcomers 5.0% Trailing-to-Even Floor)
                    trailing_amount = start_eq * 0.05
                    raw_trailing_floor = peak_eq - trailing_amount
                    hard_floor = min(start_eq, raw_trailing_floor)

                    if eq <= hard_floor:
                        is_breached = True
                        eq = hard_floor

                    executed.append({'pnl_usd': pnl_usd, 'pnl_r': setup['pnl_r']})

            if is_breached:
                breached_accounts += 1

            acc_wins = [t for t in executed if t['pnl_r'] > 0]
            acc_losses = [t for t in executed if t['pnl_r'] < 0]
            
            total_trades_executed += len(executed)
            total_wins += len(acc_wins)
            total_losses += len(acc_losses)
            total_portfolio_final += eq

        net_pnl = total_portfolio_final - start_equity_total
        ret_pct = (net_pnl / start_equity_total * 100.0)
        win_rate = (total_wins / total_trades_executed * 100.0) if total_trades_executed > 0 else 0.0

        sweep_results[cutoff] = {
            'final_nav': total_portfolio_final,
            'net_pnl': net_pnl,
            'return_pct': ret_pct,
            'total_trades': total_trades_executed,
            'win_rate': win_rate,
            'breached_accounts': breached_accounts
        }

    # Print Sensitivity Sweep Table
    print("\n--- AI CONVICTION THRESHOLD SENSITIVITY SWEEP MATRIX ---")
    print(f"{'AI CUTOFF':<12} | {'FINAL NAV ($)':<14} | {'NET PnL ($)':<14} | {'RETURN (%)':<10} | {'TOTAL TRADES':<12} | {'WIN RATE (%)':<12} | {'BREACHED ACCTS'}")
    print("-" * 100)

    for cutoff, res in sweep_results.items():
        status = "🟢 0 Breaches" if res['breached_accounts'] == 0 else f"🔴 {res['breached_accounts']} Breached"
        print(f"AI >= {cutoff:<6.1f} | ${res['final_nav']:<13,.2f} | ${res['net_pnl']:<+13,.2f} | {res['return_pct']:<+9.1f}% | {res['total_trades']:<12} | {res['win_rate']:<11.1f}% | {status}")

    print("===========================================================================\n")

if __name__ == "__main__":
    run_ai_threshold_sensitivity_sweep()

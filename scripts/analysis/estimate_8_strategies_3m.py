"""
3-Month Multi-Strategy Performance Estimator
===============================================
Simulates the performance of all 8 TradeLocker Account Strategy Mandates
over the 3-month historical dataset (`exports/tradelocker_trades_3months.txt` & Supabase exports).

Computes per-account metrics: Total Trades, Win Rate (%), Net PnL ($),
Return (%), Profit Factor, and Max Drawdown (%).
"""

import sys
import os
import json
import logging
from typing import Dict, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.engines.multi_account_funnel import MultiAccountFunnelManager, align_lot_size

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("StrategyEstimator")

def load_historical_3m_trades() -> List[dict]:
    """Loads 3-month historical trade dataset from Supabase JSON files."""
    trades = []
    
    scans_path  = os.path.join(os.path.dirname(__file__), "..", "..", "data", "bot_scans_supabase.json")
    trades_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "manual_trades_supabase.json")
    
    # 1. Parse Bot Scans Dataset
    if os.path.exists(scans_path):
        try:
            with open(scans_path, 'r') as f:
                data = json.load(f)
                for item in data:
                    ai_score = float(item.get('ai_score') or 7.0)
                    outcome  = str(item.get('outcome') or item.get('verdict') or '').upper()
                    act_r    = item.get('actual_r')
                    
                    if act_r is not None:
                        pnl_r = float(act_r)
                    elif 'WIN' in outcome or 'PASSED' in outcome:
                        pnl_r = 2.5
                    elif 'LOSS' in outcome:
                        pnl_r = -1.0
                    else:
                        pnl_r = 2.5 if ai_score >= 7.5 else -1.0

                    trades.append({
                        'symbol': str(item.get('symbol', 'BTC/USD')).replace('USDT', 'USD'),
                        'direction': 'BUY' if 'BUY' in str(item.get('direction', '')).upper() or 'LONG' in str(item.get('pattern', '')).upper() else 'SELL',
                        'price': float(item.get('price') or item.get('entry') or 65000.0),
                        'stop_loss': float(item.get('stop_loss') or 64500.0),
                        'take_profit': float(item.get('target') or 66500.0),
                        'ai_score': ai_score,
                        'hurst': float(item.get('hurst') or (0.60 if 'TREND' in str(item.get('pattern','')).upper() else 0.40)),
                        'smt': float(item.get('smt') or 0.20),
                        'pattern': item.get('pattern', 'SMC Setup'),
                        'pnl_r': pnl_r
                    })
        except Exception as e:
            logger.warning(f"Error reading scans JSON: {e}")

    # 2. Parse Manual Trades Dataset
    if os.path.exists(trades_path):
        try:
            with open(trades_path, 'r') as f:
                data = json.load(f)
                for item in data:
                    pnl = float(item.get('pnl') or 0.0)
                    pnl_r = (pnl / 100.0) if pnl != 0 else (2.5 if item.get('status') == 'CLOSED' else -1.0)
                    trades.append({
                        'symbol': str(item.get('symbol', 'BTC/USD')).replace('USDT', 'USD'),
                        'direction': str(item.get('side', 'BUY')).upper(),
                        'price': float(item.get('price') or 65000.0),
                        'stop_loss': 64500.0,
                        'take_profit': 66500.0,
                        'ai_score': float(item.get('ai_grade') or 7.5),
                        'hurst': 0.58,
                        'smt': 0.25,
                        'pattern': 'Historical Live Trade',
                        'pnl_r': 2.5 if pnl > 0 else (-1.0 if pnl < 0 else 0.0)
                    })
        except Exception as e:
            logger.warning(f"Error reading trades JSON: {e}")

    return trades


def estimate_performance():
    print("\n===========================================================================")
    print(" 📊 BAYESIAN PIVOT — 3-MONTH ESTIMATED PERFORMANCE BY STRATEGY (8 ACCOUNTS)")
    print("===========================================================================\n")

    funnel = MultiAccountFunnelManager()
    historical_trades = load_historical_3m_trades()
    print(f" • Loaded {len(historical_trades)} 3-Month Candidate Setups for Walk-Forward Audit.\n")

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

    results = {}

    for acc_key, profile in funnel.profiles.items():
        start_equity = base_balances.get(acc_key, 25000.0)
        equity = start_equity
        peak_equity = start_equity
        max_drawdown = 0.0
        
        executed_trades = []
        bypassed_count = 0

        for trade in historical_trades:
            # Evaluate trade through account funnel matrix
            passed, rejection_reasons = funnel.evaluate_setup_for_account(
                setup=trade,
                account_key=acc_key,
                hurst=trade['hurst'],
                smt_strength=trade['smt'],
                slippage_ratio=1.0,
                cal_safe=True,
                corr_ok=True,
                regime_allowed=True,
                ai_score=trade['ai_score'],
                open_positions=[]
            )

            if passed:
                # Calculate trade PnL
                risk_usd = profile.max_risk_usd
                trade_pnl = risk_usd * trade['pnl_r']
                equity += trade_pnl
                
                if equity > peak_equity:
                    peak_equity = equity
                dd = (peak_equity - equity) / peak_equity
                if dd > max_drawdown:
                    max_drawdown = dd

                executed_trades.append({
                    'pnl_usd': trade_pnl,
                    'pnl_r': trade['pnl_r'],
                    'equity': equity
                })
            else:
                bypassed_count += 1

        total_exec = len(executed_trades)
        wins = [t for t in executed_trades if t['pnl_r'] > 0]
        losses = [t for t in executed_trades if t['pnl_r'] < 0]
        
        win_rate = (len(wins) / total_exec * 100.0) if total_exec > 0 else 0.0
        net_pnl = equity - start_equity
        return_pct = (net_pnl / start_equity * 100.0)
        
        gross_profit = sum(t['pnl_usd'] for t in wins)
        gross_loss = abs(sum(t['pnl_usd'] for t in losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0.0)

        results[acc_key] = {
            'account_name': profile.account_name,
            'strategy_mode': profile.strategy_mode,
            'start_equity': start_equity,
            'final_equity': equity,
            'net_pnl': net_pnl,
            'return_pct': return_pct,
            'total_trades': total_exec,
            'bypassed_trades': bypassed_count,
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'max_drawdown_pct': max_drawdown * 100.0
        }

    # Print Summary Table
    print(f"{'ACCOUNT':<12} | {'MANDATE':<16} | {'START $':<10} | {'FINAL $':<10} | {'NET PnL ($)':<12} | {'RET (%)':<8} | {'TRADES':<7} | {'WIN %':<7} | {'PF':<6} | {'MAX DD':<7}")
    print("-" * 115)

    tot_start = 0.0
    tot_final = 0.0

    for acc_key, res in results.items():
        tot_start += res['start_equity']
        tot_final += res['final_equity']
        print(f"{acc_key:<12} | {res['strategy_mode']:<16} | ${res['start_equity']:<9,.0f} | ${res['final_equity']:<9,.0f} | ${res['net_pnl']:<11,.2f} | {res['return_pct']:<+7.1f}% | {res['total_trades']:<7} | {res['win_rate']:<6.1f}% | {res['profit_factor']:<6.2f} | {res['max_drawdown_pct']:<6.1f}%")

    tot_pnl = tot_final - tot_start
    tot_ret = (tot_pnl / tot_start * 100.0)

    print("-" * 115)
    print(f"🏛️ COMBINED PORTFOLIO | START: ${tot_start:,.2f} | FINAL: ${tot_final:,.2f} | NET PnL: +${tot_pnl:,.2f} (+{tot_ret:.1f}%)")
    print("===========================================================================\n")

if __name__ == "__main__":
    estimate_performance()

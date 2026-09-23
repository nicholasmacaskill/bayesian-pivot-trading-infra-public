#!/usr/bin/env python3
"""
================================================================================
🏛️ BAYESIAN PIVOT // LIVE TRADELOCKER FLEET VITALS MONITOR
================================================================================
Queries the live TradeLocker broker API across all configured accounts to return
authoritative real-time equity, balance, drawdown floors, true buffer, and
loss runway. Eliminates reliance on stale markdown snapshots.
"""

import os
import sys
import json
import logging
from typing import List, Dict, Any
from dotenv import load_dotenv

# Ensure repo root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Suppress debug logs
logging.basicConfig(level=logging.WARNING)

load_dotenv(".env")
load_dotenv(".env.local")

from src.clients.tl_client import TradeLockerClient
from src.core.config import Config


def get_live_fleet_vitals() -> List[Dict[str, Any]]:
    """
    Directly queries TradeLocker broker API across all configured accounts.
    Returns structured real-time metrics for every account.
    """
    tl = TradeLockerClient()
    accounts_data = []

    # Hard Floors & Base Risk mapping from Config / AGENTS.md rules
    FLOOR_RULES = {
        "s79qv3xetj@upcomers.com": {"floor": 25000.0, "tier": "$25k", "risk": 35.0, "payout_target": 27000.0, "account_num": 1},
        "498svcbpfi@upcomers.com": {"floor": 47500.0, "tier": "$50k", "risk": 70.0, "payout_target": 54000.0, "account_num": 2},
        "q20gxm287x@upcomers.com": {"floor": 23750.0, "tier": "$25k", "risk": 50.0, "payout_target": 27000.0, "account_num": 3},
        "vkrbpwdprh@upcomers.com": {"floor": 9500.0,  "tier": "$10k", "risk": 0.0,  "payout_target": 10800.0, "account_num": 4},
        "hnr10rtj4k@upcomers.com": {"floor": 9500.0,  "tier": "$10k", "risk": 0.0,  "payout_target": 10800.0, "account_num": 5},
        "dwundrtxjv@upcomers.com": {"floor": 47500.0, "tier": "$50k", "risk": 80.0, "payout_target": 54000.0, "account_num": 6},
        "875do5esrd@upcomers.com": {"floor": 23750.0, "tier": "$25k", "risk": 35.0, "payout_target": 27000.0, "account_num": 7},
        "h4sj53tg4f@upcomers.com": {"floor": 9500.0,  "tier": "$10k", "risk": 0.0,  "payout_target": 10800.0, "account_num": 8},
        "jfcuue7er3@upcomers.com": {"floor": 47500.0, "tier": "$50k", "risk": 100.0, "payout_target": 54000.0, "account_num": 9},
    }

    import requests

    for i, helper in enumerate(tl.helpers):
        email = helper.email
        rule = FLOOR_RULES.get(email, {"floor": 25000.0, "tier": "Unknown", "risk": 35.0, "payout_target": 27000.0, "account_num": i+1})
        
        try:
            helper.login()
            url = f"{helper.base_url}/backend-api/auth/jwt/all-accounts"
            resp = requests.get(url, headers=helper._get_headers(auth=True), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                for acc in data.get('accounts', []):
                    acc_id = str(acc.get('id', 'N/A'))
                    status = str(acc.get('status', 'ACTIVE')).upper()
                    balance = float(acc.get('accountBalance', 0.0))
                    equity = float(acc.get('projectedEquity') or balance)
                    floor = rule["floor"]
                    base_risk = rule["risk"]
                    buffer_usd = max(0.0, equity - floor)
                    runway = round(buffer_usd / base_risk, 1) if base_risk > 0 else 0.0
                    target = rule["payout_target"]
                    remaining_to_payout = max(0.0, target - equity)

                    accounts_data.append({
                        "account_num": rule["account_num"],
                        "email": email,
                        "account_id": acc_id,
                        "tier": rule["tier"],
                        "status": status,
                        "balance": balance,
                        "equity": equity,
                        "floor": floor,
                        "buffer_usd": buffer_usd,
                        "base_risk": base_risk,
                        "loss_runway": runway,
                        "payout_target": target,
                        "remaining_to_payout": remaining_to_payout
                    })
            else:
                accounts_data.append({
                    "account_num": rule["account_num"],
                    "email": email,
                    "account_id": "ERROR",
                    "tier": rule["tier"],
                    "status": f"HTTP_{resp.status_code}",
                    "balance": 0.0,
                    "equity": 0.0,
                    "floor": rule["floor"],
                    "buffer_usd": 0.0,
                    "base_risk": rule["risk"],
                    "loss_runway": 0.0,
                    "payout_target": rule["payout_target"],
                    "remaining_to_payout": 0.0
                })
        except Exception as err:
            accounts_data.append({
                "account_num": rule["account_num"],
                "email": email,
                "account_id": "EXCEPTION",
                "tier": rule["tier"],
                "status": str(err)[:20],
                "balance": 0.0,
                "equity": 0.0,
                "floor": rule["floor"],
                "buffer_usd": 0.0,
                "base_risk": rule["risk"],
                "loss_runway": 0.0,
                "payout_target": rule["payout_target"],
                "remaining_to_payout": 0.0
            })

    # Sort by account_num
    accounts_data.sort(key=lambda x: x["account_num"])
    return accounts_data


def print_fleet_summary(accounts: List[Dict[str, Any]]):
    """Prints a beautiful, clean ASCII table of live fleet vitals."""
    print("\n╔══════════════════════════════════════════════════════════════════════════════════════════════════════╗")
    print("║                     🏛️  BAYESIAN PIVOT // LIVE BROKER FLEET STATUS (TRADELOCKER)                      ║")
    print("╚══════════════════════════════════════════════════════════════════════════════════════════════════════╝")
    print(f"{'Acct':<5} {'Tier':<6} {'Status':<16} {'Live Balance':<14} {'Floor':<11} {'Buffer':<12} {'Base Risk':<11} {'Runway':<10} {'To Target':<12}")
    print("─" * 102)

    total_active_equity = 0.0
    total_active_buffer = 0.0

    for a in accounts:
        status_display = a['status']
        if a['status'] == 'ACTIVE':
            total_active_equity += a['equity']
            total_active_buffer += a['buffer_usd']
            acct_str = f"#{a['account_num']} ({a['email'].split('@')[0]})"
        else:
            acct_str = f"#{a['account_num']} [QUARANTINED]"

        print(
            f"#{a['account_num']:<4} "
            f"{a['tier']:<6} "
            f"{status_display:<16} "
            f"${a['equity']:>10,.2f}   "
            f"${a['floor']:>8,.2f}  "
            f"+${a['buffer_usd']:>8,.2f}   "
            f"${a['base_risk']:>6,.2f}     "
            f"{a['loss_runway']:>5.1f} R   "
            f"${a['remaining_to_payout']:>9,.2f}"
        )

    print("─" * 102)
    print(f"💰 Total Active Funded Equity (Accounts 1, 2, 3, 6, 7, 9): ${total_active_equity:,.2f}")
    print(f"🛡️ Total Active Buffer Above Floor:                     +${total_active_buffer:,.2f}")
    print("═" * 102 + "\n")


if __name__ == "__main__":
    vitals = get_live_fleet_vitals()
    if "--json" in sys.argv:
        print(json.dumps(vitals, indent=2))
    else:
        print_fleet_summary(vitals)

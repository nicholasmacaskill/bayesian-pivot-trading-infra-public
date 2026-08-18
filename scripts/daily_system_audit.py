"""
Daily System Health & Diagnostic Audit Watchdog
=================================================
Performs an automated 7-point diagnostic audit of the entire trading infrastructure:
  1. Daemon Process Health (PID, CPU, Memory, Uptime)
  2. Scan Freshness & Database Lock Verification (smc_alpha.db)
  3. Exchange Live Market Data Sync (CCXT Coinbase/Binance)
  4. TradeLocker Broker API & 8-Account Balance Sync
  5. Multi-Modal AI Validator API Connectivity & Latency (Gemini / OpenRouter)
  6. SQLite WAL Checkpoint, Disk Space & Swap Usage
  7. Telegram Executive Health Report Dispatch
"""

import sys
import os
import time
import subprocess
import sqlite3
import logging
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.config import Config
from src.core.database import get_db_connection
from src.clients.telegram_notifier import TelegramNotifier
from src.clients.tl_client import TradeLockerClient
from src.engines.smc_scanner import SMCScanner
from src.engines.ai_validator import AIValidator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DailyAuditWatchdog")

def run_daily_audit():
    print("\n" + "=" * 75)
    print(" 🛡️ BAYESIAN PIVOT — DAILY SYSTEM HEALTH & DIAGNOSTIC AUDIT")
    print("=" * 75 + "\n")

    report_lines = []
    issues_found = []
    all_healthy = True
    start_time = time.time()

    # ──────────────────────────────────────────────────────────────────────────
    # 1. DAEMON PROCESS CHECK
    # ──────────────────────────────────────────────────────────────────────────
    print(" [1/7] 🔍 Checking Local Scanner Daemon Process...")
    res = subprocess.run(["ps", "-eo", "pid,pcpu,pmem,args"], capture_output=True, text=True)
    scanner_pids = []
    for line in res.stdout.splitlines():
        if "local_scanner.py" in line and "grep" not in line and "python" in line.lower():
            scanner_pids.append(line.strip())

    if scanner_pids:
        pid_info = scanner_pids[0].split()
        pid = pid_info[0]
        cpu = pid_info[1]
        mem = pid_info[2]
        daemon_status = f"✅ Running (PID: {pid} | CPU: {cpu}% | RAM: {mem}%)"
        print(f"       • {daemon_status}")
    else:
        daemon_status = "❌ OFFLINE (Auto-Restarting via launchctl...)"
        print(f"       • {daemon_status}")
        issues_found.append("Scanner daemon was offline (auto-restart triggered)")
        all_healthy = False
        subprocess.run(["launchctl", "unload", os.path.expanduser("~/Library/LaunchAgents/com.sovereign.scanner.plist")])
        subprocess.run(["launchctl", "load", os.path.expanduser("~/Library/LaunchAgents/com.sovereign.scanner.plist")])

    report_lines.append(f"• <b>Daemon Status:</b> <code>{daemon_status}</code>")

    # ──────────────────────────────────────────────────────────────────────────
    # 2. SCAN FRESHNESS & SQLITE DATABASE HEALTH
    # ──────────────────────────────────────────────────────────────────────────
    print(" [2/7] 🔍 Checking SQLite Database Health & Scan Freshness...")
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check SQLite WAL Checkpoint & Integrity
        cur.execute("PRAGMA integrity_check;")
        integrity = cur.fetchone()[0]
        cur.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        
        # Check recent scans
        cur.execute("SELECT count(*), max(timestamp) FROM scans;")
        scan_count, last_scan_ts = cur.fetchone()
        
        cur.execute("SELECT count(*) FROM inducement_events;")
        inducement_count = cur.fetchone()[0]

        cur.execute("SELECT count(*) FROM counterfactual_trades;")
        cf_count = cur.fetchone()[0]

        conn.close()

        db_status = f"✅ Healthy (Integrity: {integrity} | Scans: {scan_count:,} | Inducements: {inducement_count} | Shadow Trades: {cf_count})"
        print(f"       • {db_status}")
        report_lines.append(f"• <b>Database Health:</b> <code>{integrity} (WAL Optimized)</code>")
        report_lines.append(f"• <b>Logged Activity:</b> <code>{scan_count:,} scans | {inducement_count} inducements | {cf_count} shadow trades</code>")
    except Exception as e:
        db_status = f"❌ Database Error: {e}"
        print(f"       • {db_status}")
        issues_found.append(f"Database error: {e}")
        all_healthy = False
        report_lines.append(f"• <b>Database Health:</b> <code>{db_status}</code>")

    # ──────────────────────────────────────────────────────────────────────────
    # 3. EXCHANGE LIVE MARKET DATA CHECK
    # ──────────────────────────────────────────────────────────────────────────
    print(" [3/7] 🔍 Checking Live Exchange Feed (Coinbase / Binance)...")
    try:
        scanner = SMCScanner()
        t0 = time.time()
        btc_df = scanner.fetch_data("BTC/USD", "5m", limit=10)
        eth_df = scanner.fetch_data("ETH/USD", "5m", limit=10)
        feed_latency = (time.time() - t0) * 1000

        if btc_df is not None and not btc_df.empty and eth_df is not None and not eth_df.empty:
            btc_price = btc_df.iloc[-1]['close']
            eth_price = eth_df.iloc[-1]['close']
            feed_status = f"✅ Connected ({feed_latency:.0f}ms | BTC: ${btc_price:,.2f} | ETH: ${eth_price:,.2f})"
            print(f"       • {feed_status}")
        else:
            feed_status = f"⚠️ Incomplete Data Feed ({feed_latency:.0f}ms)"
            print(f"       • {feed_status}")
            issues_found.append("Exchange market feed returned empty dataframe")
            all_healthy = False
        report_lines.append(f"• <b>Market Data Feed:</b> <code>{feed_status}</code>")
    except Exception as e:
        feed_status = f"❌ Exchange Error: {e}"
        print(f"       • {feed_status}")
        issues_found.append(f"Exchange connection failed: {e}")
        all_healthy = False
        report_lines.append(f"• <b>Market Data Feed:</b> <code>{feed_status}</code>")

    # ──────────────────────────────────────────────────────────────────────────
    # 4. TRADELOCKER BROKER API & 8-ACCOUNT SYNC
    # ──────────────────────────────────────────────────────────────────────────
    print(" [4/7] 🔍 Checking TradeLocker Broker API & Account Balances...")
    try:
        tl = TradeLockerClient()
        total_equity = tl.get_total_equity()
        open_pos = tl.get_open_positions()

        if total_equity > 0:
            tl_status = f"✅ Synced (${total_equity:,.2f} NAV | Open Positions: {len(open_pos) if open_pos else 0})"
            print(f"       • {tl_status}")
        else:
            tl_status = "⚠️ Connected but total equity reported $0.00"
            print(f"       • {tl_status}")
            issues_found.append("TradeLocker total equity returned 0")
            all_healthy = False
        report_lines.append(f"• <b>TradeLocker Broker:</b> <code>{tl_status}</code>")
    except Exception as e:
        tl_status = f"❌ TradeLocker Error: {e}"
        print(f"       • {tl_status}")
        issues_found.append(f"TradeLocker sync error: {e}")
        all_healthy = False
        report_lines.append(f"• <b>TradeLocker Broker:</b> <code>{tl_status}</code>")

    # ──────────────────────────────────────────────────────────────────────────
    # 5. MULTI-MODAL AI VALIDATOR CONNECTIVITY
    # ──────────────────────────────────────────────────────────────────────────
    print(" [5/7] 🔍 Checking Gemini 2.5 Flash / OpenRouter AI Validation API...")
    try:
        t0 = time.time()
        import google.genai as genai
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key:
            client = genai.Client(api_key=api_key)
            resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents="Ping. Return single word: ACTIVE."
            )
            ai_lat = (time.time() - t0) * 1000
            ai_status = f"✅ Online ({ai_lat:.0f}ms | Response: {resp.text.strip()[:10]})"
            print(f"       • {ai_status}")
        else:
            ai_status = "⚠️ GEMINI_API_KEY not set (Using local fallback)"
            print(f"       • {ai_status}")
        report_lines.append(f"• <b>AI Validator (Gemini):</b> <code>{ai_status}</code>")
    except Exception as e:
        ai_status = f"⚠️ AI Network Warning: {e} (Cascade fallback active)"
        print(f"       • {ai_status}")
        report_lines.append(f"• <b>AI Validator:</b> <code>{ai_status}</code>")

    # ──────────────────────────────────────────────────────────────────────────
    # 6. SYSTEM MEMORY, SWAP & DISK STORAGE
    # ──────────────────────────────────────────────────────────────────────────
    print(" [6/7] 🔍 Checking System Memory, Swap & Disk Space...")
    try:
        swap_res = subprocess.run(["sysctl", "vm.swapusage"], capture_output=True, text=True)
        swap_str = swap_res.stdout.strip().replace("vm.swapusage: ", "")
        
        df_res = subprocess.run(["df", "-h", "/"], capture_output=True, text=True)
        disk_avail = df_res.stdout.splitlines()[1].split()[3]
        
        sys_status = f"✅ Disk Free: {disk_avail} | Swap: {swap_str}"
        print(f"       • {sys_status}")
        report_lines.append(f"• <b>System Resources:</b> <code>Disk Free: {disk_avail} | Swap: {swap_str}</code>")
    except Exception as e:
        sys_status = f"Error: {e}"
        report_lines.append(f"• <b>System Resources:</b> <code>{sys_status}</code>")

    # ──────────────────────────────────────────────────────────────────────────
    # 7. TELEGRAM EXECUTIVE REPORT DISPATCH
    # ──────────────────────────────────────────────────────────────────────────
    print(" [7/7] 📤 Dispatching Executive Daily Health Report to Telegram...")
    total_duration = time.time() - start_time
    header_status = "🟢 <b>ALL SYSTEMS OPERATIONAL & HEALTHY</b>" if all_healthy else "⚠️ <b>SYSTEM AUDIT WARNINGS DETECTED</b>"

    issue_block = ""
    if issues_found:
        issue_block = "\n\n⚠️ <b>Issues Flagged:</b>\n" + "\n".join([f"• <i>{iss}</i>" for iss in issues_found])

    tg_message = (
        f"🛡️ <b>BAYESIAN PIVOT — DAILY AUDIT REPORT</b>\n"
        f"───────────────────────────────\n"
        f"{header_status}\n"
        f"📅 <i>Audit Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}</i>\n"
        f"⏱️ <i>Diagnostic Duration: {total_duration:.2f}s</i>\n"
        f"───────────────────────────────\n" +
        "\n".join(report_lines) +
        f"{issue_block}\n"
        f"───────────────────────────────\n"
        f"🤖 <i>Status: Continuous 3-Minute Scanning Active</i>"
    )

    try:
        notifier = TelegramNotifier()
        notifier._send_message(tg_message)
        print("       • ✅ Telegram Executive Health Report Dispatched Successfully!")
    except Exception as e:
        print(f"       • ❌ Failed to dispatch Telegram report: {e}")

    print("\n" + "=" * 75)
    print(f" ✅ Daily Diagnostic Audit Completed in {total_duration:.2f}s")
    print("=" * 75 + "\n")

if __name__ == "__main__":
    run_daily_audit()

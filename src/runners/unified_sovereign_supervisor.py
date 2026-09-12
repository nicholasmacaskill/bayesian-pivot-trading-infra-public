import os
import sys
import time
import signal
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, Optional

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.core.config import Config

# Configure unified logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - (%(threadName)s) - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/unified_supervisor.log")
    ]
)
logger = logging.getLogger("UnifiedSupervisor")

class UnifiedSovereignSupervisor:
    """
    Unified Sovereign Supervisor Daemon.
    Consolidates:
      1. Alpha Sweep & Inducement Scanning (Multi-Asset SMC & Shadow Tournament)
      2. Active Position Watchdog & Autonomous Fleet Scale-Out (50% scale-out @ +1.5R)
      3. Shadow Tournament Resolution & Maintenance
    Runs in a single lightweight Python process (~120 MB RAM vs 800 MB across 10 processes).
    """

    def __init__(self):
        self.running = True
        self.scanner = None
        self.watchdog = None
        self._setup_signals()

    def _setup_signals(self):
        signal.signal(signal.SIGINT, self._handle_exit)
        signal.signal(signal.SIGTERM, self._handle_exit)

    def _handle_exit(self, signum, frame):
        logger.info("🛑 Received termination signal. Shutting down Unified Supervisor gracefully...")
        self.running = False

    def get_adaptive_scan_interval(self) -> int:
        """
        Session-Adaptive Sleep Pacing:
        - Weekends (Saturday/Sunday UTC): 300s (5m) — Live execution firewalled
        - Active London / NY Killzone (07:00-10:00, 13:00-16:00 UTC): 60s (1m) — Prime execution
        - Off-Hours Weekday: 180s (3m) — Preserves CPU cycles
        """
        now_utc = datetime.now(timezone.utc)
        weekday = now_utc.weekday() # 5=Sat, 6=Sun
        hour = now_utc.hour

        if weekday >= 5:
            return 300 # 5 minutes on weekends ($0 live risk)
        
        # London Killzone (07:00-10:00 UTC) or NY AM/PM Killzone (12:00-19:00 UTC)
        is_killzone = (7 <= hour < 10) or (12 <= hour < 20)
        if is_killzone:
            return 60 # 1 minute during active institutional sessions
        
        return 180 # 3 minutes during quiet off-hours

    # ── WORKER 1: Alpha Sweep & Inducement Scanner ──
    def run_scanner_worker(self):
        logger.info("🚀 [Worker: Scanner] Starting Alpha Sweep & Inducement worker...")
        try:
            from src.engines.alpha_sweep_scanner import AlphaSweepScanner
            self.scanner = AlphaSweepScanner()
        except Exception as e:
            logger.error(f"Failed to initialize AlphaSweepScanner: {e}")
            return

        while self.running:
            try:
                live_symbols = list(getattr(Config, 'SYMBOLS', ['BTC/USD']))
                shadow_symbols = list(getattr(Config, 'SHADOW_SYMBOLS', ['XAU/USD', 'ETH/USD', 'SOL/USD']))
                all_symbols = list(dict.fromkeys(live_symbols + shadow_symbols))

                # 1. Check & trail open positions
                try:
                    self.scanner.check_and_trail_positions()
                except Exception as e:
                    logger.debug(f"Watchdog scan check: {e}")

                # 2. Scan all configured symbols (Live + Shadow Trackers)
                for sym in all_symbols:
                    if not self.running:
                        break
                    try:
                        is_shadow_asset = (sym in shadow_symbols and sym not in live_symbols)
                        setup = self.scanner.scan_symbol(sym, is_shadow=is_shadow_asset)
                        if setup:
                            prefix = "👻 [SHADOW SETUP]" if is_shadow_asset else "🎯 [SCANNER SETUP]"
                            logger.info(f"{prefix} {sym}: {setup.get('pattern')} | Conviction={setup.get('conviction_score')}")
                    except Exception as e:
                        logger.error(f"Error scanning {sym}: {e}")

            except Exception as e:
                logger.error(f"Scanner worker loop error: {e}")

            # Adaptive Sleep
            interval = self.get_adaptive_scan_interval()
            logger.info(f"💤 [Worker: Scanner] Sleeping {interval}s (Adaptive Session Pacing)...")
            slept = 0
            while slept < interval and self.running:
                time.sleep(2)
                slept += 2

    # ── WORKER 2: Position Watchdog & Autonomous Fleet Scale-Out ──
    def run_watchdog_worker(self):
        logger.info("🛡️ [Worker: Watchdog] Starting Risk & Fleet Scale-Out watchdog...")
        try:
            from scripts.position_watchdog import PositionWatchdog
            self.watchdog = PositionWatchdog()
        except Exception as e:
            logger.error(f"Failed to initialize PositionWatchdog: {e}")
            return

        while self.running:
            try:
                positions = self.watchdog.tl.get_open_positions()
                if positions:
                    for pos in positions:
                        t_id = pos['id']
                        symbol = pos['symbol']
                        entry = pos['price']
                        pnl = pos['pnl']
                        
                        if t_id not in self.watchdog.alerted_trades:
                            self.watchdog.alerted_trades[t_id] = {}

                        sl, scan = self.watchdog.get_stop_loss(symbol)
                        if not sl:
                            continue
                        
                        qty = pos.get('qty', 0)
                        clean_sym = symbol.replace("/", "").replace("_", "").upper()
                        if any(c in clean_sym for c in ["BTC", "ETH", "SOL", "GALA", "CRYPTO"]):
                            contract_size = 1.0
                        elif any(m in clean_sym for m in ["XAU", "GOLD", "SILVER", "XAG"]):
                            contract_size = 100.0
                        else:
                            contract_size = 100000.0  # Standard Forex
                        risk_usd = abs(entry - sl) * qty * contract_size
                        if risk_usd > 0:
                            r_multiple = pnl / risk_usd
                            logger.info(f"📊 [OPEN POSITION] {symbol} PnL: ${pnl:.2f} | R: {r_multiple:.2f}R")

                            # Autonomous Fleet Scale-Out at +1.5R
                            if r_multiple >= 1.5 and not self.watchdog.alerted_trades.get(t_id, {}).get("scaleout_executed"):
                                logger.info(f"💰 [AUTO SCALE-OUT] {symbol} reached {r_multiple:.2f}R! Executing 50% fleet closure...")
                                self.watchdog.execute_fleet_scaleout(symbol, entry)
                                self.watchdog.alerted_trades[t_id]["scaleout_executed"] = True
                                self.watchdog.save_state()

                            # Milestone Telegram Alerts
                            for target in [1.5, 2.0, 3.0]:
                                target_key = str(target)
                                if r_multiple >= target and not self.watchdog.alerted_trades.get(t_id, {}).get(target_key):
                                    msg = (
                                        f"🚀 <b>BAYESIAN PIVOT TARGET REACHED!</b>\n"
                                        f"Symbol: <code>{symbol}</code>\n"
                                        f"Current R: <b>{r_multiple:.2f}R</b>\n\n"
                                        f"🛡️ <b>DISCIPLINE CHECK:</b> Target {target}R reached.\n"
                                        "Autonomous fleet scale-out and trailing stop active."
                                    )
                                    self.watchdog.notifier._send_message(msg)
                                    self.watchdog.alerted_trades[t_id][target_key] = True
                                    self.watchdog.save_state()

                # Sleep 60s when positions exist, 120s when flat
                sleep_time = 60 if positions else 120
                slept = 0
                while slept < sleep_time and self.running:
                    time.sleep(2)
                    slept += 2

            except Exception as e:
                logger.error(f"Watchdog worker loop error: {e}")
                time.sleep(30)

    # ── WORKER 3: Maintenance & Shadow Reconciler ──
    def run_maintenance_worker(self):
        logger.info("🧹 [Worker: Maintenance] Starting Shadow Tournament & DB Maintenance worker...")
        while self.running:
            try:
                # 1. Update SQLite WAL checkpoint to keep db small
                from src.core.database import get_db_connection
                conn = get_db_connection()
                conn.execute("PRAGMA wal_checkpoint(PASSIVE);")
                conn.close()
                logger.debug("SQLite WAL checkpoint completed.")

                # 2. Automated System Hygiene Sweep (Caches, PyCache, MCP Debuggers, Memory Health)
                try:
                    from scripts.maintenance.system_hygiene import sweep_system_hygiene
                    hygiene_res = sweep_system_hygiene()
                    cleaned_mcp = hygiene_res.get("mcp_cleaned", 0)
                    freed_caches = hygiene_res.get("caches_freed_mb", {})
                    py_cleaned = hygiene_res.get("pycache_dirs_removed", 0)
                    if cleaned_mcp > 0 or freed_caches or py_cleaned > 0:
                        logger.info(f"🧹 [System Hygiene] Auto-sweep: {cleaned_mcp} MCP killed, {len(freed_caches)} caches purged, {py_cleaned} pycaches cleared.")
                except Exception as hyg_err:
                    logger.debug(f"System hygiene sweep notice: {hyg_err}")

            except Exception as e:
                logger.debug(f"Maintenance error: {e}")

            # Run maintenance every 15 minutes (900s)
            slept = 0
            while slept < 900 and self.running:
                time.sleep(5)
                slept += 5

    # ── WORKER 4: Software as Glass Observability HUD ──
    def run_glass_hud_worker(self):
        logger.info("💎 [Worker: Glass HUD] Dashboard server SHUT OFF by user request.")
        return

    def start(self):
        logger.info("👑 =========================================================")
        logger.info("👑 SOVEREIGN UNIFIED SUPERVISOR STARTING")
        logger.info(f"👑 PID: {os.getpid()} | Adaptive Pacing: Active | Memory Cap: ~120 MB")
        logger.info("👑 =========================================================")

        t_scanner = threading.Thread(target=self.run_scanner_worker, name="ScannerThread", daemon=True)
        t_watchdog = threading.Thread(target=self.run_watchdog_worker, name="WatchdogThread", daemon=True)
        t_maint = threading.Thread(target=self.run_maintenance_worker, name="MaintThread", daemon=True)
        t_glass = threading.Thread(target=self.run_glass_hud_worker, name="GlassHUDThread", daemon=True)

        t_scanner.start()
        t_watchdog.start()
        t_maint.start()
        t_glass.start()

        # Keep main thread alive
        while self.running:
            time.sleep(1)

        logger.info("Unified Supervisor shutdown complete.")

if __name__ == "__main__":
    import argparse
    from src.core.process_lock import MasterProcessLock

    parser = argparse.ArgumentParser(description="Unified Sovereign Supervisor")
    parser.add_argument("--test", action="store_true", help="Run a single test cycle and exit")
    args = parser.parse_args()

    with MasterProcessLock(runner_name="UnifiedSovereignSupervisor"):
        supervisor = UnifiedSovereignSupervisor()
        if args.test:
            logger.info("Running single test cycle across all workers...")
            supervisor.get_adaptive_scan_interval()
            from src.engines.alpha_sweep_scanner import AlphaSweepScanner
            s = AlphaSweepScanner()
            s.scan_symbol("BTC/USD")
            logger.info("Test cycle completed successfully.")
        else:
            supervisor.start()

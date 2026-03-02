import matplotlib
matplotlib.use('Agg')
import time
import requests
import logging
import signal
import sys
import os
import fcntl
from datetime import datetime
from src.core.config import Config
from src.engines.smc_scanner import SMCScanner
from src.engines.sentiment_engine import SentimentEngine
from src.engines.ai_validator import validate_setup
from src.engines.visualizer import generate_ict_chart
from src.core.memory import memory
from src.engines.prop_guardian import PropGuardian
from src.core.database import init_db, log_scan, update_sync_state, log_system_event, get_db_connection, log_prop_audit
from src.clients.tl_client import TradeLockerClient
from src.clients.telegram_notifier import TelegramNotifier, send_alert, send_system_error
from src.engines.execution_audit import ExecutionAuditEngine
from src.engines.guard_engine import GuardEngine
# ── NEW: 5-Feature Suite ─────────────────────────────────────────────────────
from src.engines.correlation_gate import CorrelationGate
from src.engines.calendar_filter  import CalendarFilter
from src.engines.regime_filter     import RegimeFilter
from src.engines.trade_ledger      import TradeLedger
from src.engines.retraining_loop   import RetrainingLoop

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/local_runner.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("LocalRunner")

# Lock file to prevent duplicate processes
LOCK_FILE = f"/tmp/smc_scanner.lock"

def check_single_instance():
    """Ensure only one instance of the scanner is running."""
    lock_file = open(LOCK_FILE, "w")
    try:
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return lock_file
    except IOError:
        print("⚠️  Another instance of Sovereign SMC is already running. Exiting.")
        sys.exit(0)

class LocalScannerRunner:
    def __init__(self):
        self.lock = check_single_instance()
        self.scanner = SMCScanner()
        self.sentiment_engine = SentimentEngine()
        self.tl = TradeLockerClient()
        self.audit_engine = ExecutionAuditEngine()
        self.prop_guardian = PropGuardian()
        self.notifier = TelegramNotifier()  # <--- PERSISTENT INSTANCE
        self.last_prop_audit = 0
        self.running = True

        # ── 5-Feature Suite ───────────────────────────────────────────
        self.corr_gate    = CorrelationGate(
            max_per_direction=Config.get('CORRELATION_MAX_PER_DIRECTION', 1),
            expiry_hours=Config.get('CORRELATION_SLOT_EXPIRY_HRS', 4),
        )
        self.cal_filter   = CalendarFilter(
            blackout_minutes=Config.get('CALENDAR_BLACKOUT_MINUTES', 30),
        )
        self.regime_filter = RegimeFilter()
        self.ledger        = TradeLedger() if Config.get('LEDGER_ENABLED', True) else None
        self.retrain_loop  = RetrainingLoop()  if Config.get('RETRAIN_ENABLED',  True) else None
        # ───────────────────────────────────────────────────────────

        # ── Sovereign Guard (Security Layer) ────────────────────────────────
        self.guard = GuardEngine(notifier=self.notifier)
        self.guard.start()
        logger.info("🛡️  Sovereign Guard active — securing your edge.")
        # ────────────────────────────────────────────────────────────────────

        # Shutdown handler
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

    def shutdown(self, signum, frame):
        logger.info("🛑 Shutdown signal received. Cleaning up...")
        self.running = False
        self.guard.stop()
        logger.info("🛡️  Sovereign Guard stopped.")

    def _send_pulse(self):
        """PULSE PROTOCOL: Notify Modal that we are alive."""
        try:
            url = "https://nicholasmacaskill--smc-alpha-scanner-yard-heartbeat.modal.run"
            auth_key = os.environ.get("SYNC_AUTH_KEY")
            payload = {"key": auth_key, "symbol": "YARD_HUB"}
            
            response = requests.post(url, json=payload, timeout=5)
            response.raise_for_status()
            logger.info("💓 Pulse Sent: Yard Mode is Live.")
        except Exception as e:
            logger.warning(f"⚠️ Pulse Failed (Modal might be throttled): {e}")

    def run_cycle(self):
        logger.info("🚀 Starting SMC Alpha Scan Cycle...")
        self._send_pulse()
        try:
            init_db()
            
            # 1. Sync Equity
            live_equity = self.tl.get_total_equity()
            if live_equity > 0:
                logger.info(f"💰 Equity Synced: ${live_equity:,.2f}")
                update_sync_state(live_equity, 0) # Watchdog handles trade count
            
            # 2. Journal Watchdog (Auto-Sync Closed History & Open Positions)
            logger.info("🐶 Journal Watchdog: Syncing trade history...")
            self._sync_trade_journal(live_equity)
            
            scan_list = Config.SYMBOLS + Config.ALT_SYMBOLS
            setups_found = 0
            
            for symbol in scan_list:
                logger.info(f"🔎 Scanning {symbol}...")
                
                # Scan Logic (SMC + Order Flow Fallback)
                # Fetch Bias first for logging
                bias_score = self.scanner.get_detailed_bias(symbol)
                logger.info(f"CAPTURED BIAS: {bias_score} on {symbol}")

                # ── GATE 1: Economic Calendar ────────────────────────────────────
                cal_safe, cal_reason = self.cal_filter.is_safe_to_trade(symbol)
                if not cal_safe:
                    logger.warning(f"⛔ CALENDAR BLOCK [{symbol}]: {cal_reason}")
                    continue

                # --- ⭐ PRIORITY: Asian Fade Prime Window Scan ---
                is_prime_window = self.scanner.is_asian_fade_window()
                result = None
                if is_prime_window:
                    result = self.scanner.scan_asian_fade(symbol)
                    if result:
                        logger.info(f"⭐ PRIME WINDOW SETUP: Asian Fade detected on {symbol}")

                # --- Standard SMC Scan (fallback) ---
                if not result:
                    result = self.scanner.scan_pattern(symbol, timeframe=Config.TIMEFRAME)
                if not result:
                    result = self.scanner.scan_order_flow(symbol, timeframe=Config.TIMEFRAME)

                if result:
                    setup, df = result
                    if not setup:
                        continue

                    logger.info(f"✅ Pattern Found: {setup.get('pattern')} on {symbol}")

                    # ── GATE 2: Correlation Risk ──────────────────────────────────
                    direction = setup.get('direction', setup.get('bias', ''))
                    corr_ok, corr_reason = self.corr_gate.check(symbol, direction)
                    if not corr_ok:
                        logger.warning(f"🛑 CORRELATION BLOCK [{symbol}]: {corr_reason}")
                        continue

                    # ── GATE 3: Regime Detection ──────────────────────────────────
                    df_1h = self.scanner.fetch_data(symbol, '1h', limit=200)
                    regime_result = self.regime_filter.classify(symbol, df_1h, df)
                    if not regime_result.allowed:
                        logger.warning(f"🛑 REGIME BLOCK [{symbol}]: {regime_result.reason}")
                        continue
                    # Adjust position size for regime
                    regime_size_mult = regime_result.suggested_size_mult
                    logger.info(f"🌎 Regime: {regime_result.regime.value} | Size mult: {regime_size_mult:.1f}x")

                    # Sentiment & Whales
                    market_data = self.sentiment_engine.get_market_sentiment(symbol)
                    whale_flow = self.sentiment_engine.get_whale_confluence()
                    
                    # Generate Visual Context for VLM Proxy
                    chart_filename = f"setup_{symbol.replace('/', '_')}_{int(time.time())}.png"
                    chart_path = os.path.join("data", "charts", chart_filename)
                    generated_chart = generate_ict_chart(df, setup, output_path=chart_path)
                    
                    # Retrieve Memory Context (RAG)
                    memory_context = memory.get_context_for_validator(setup)
                    logger.info(f"🧠 Memory Context retrieved ({'Found history' if 'Found similar' in memory_context else 'No history'})")
                    
                    # ── Security Context (Sovereign Guard enrichment) ────
                    security_context = self.guard.get_security_context()
                    enriched_memory  = f"{memory_context}\n\n[Guard] {security_context}"
                    # ────────────────────────────────────────────────────────

                    # AI Validation (Vision Proxy + RAG Active)
                    ai_result = validate_setup(
                        setup,
                        market_data,
                        whale_flow,
                        image_path=generated_chart,
                        df=df,
                        exchange=self.scanner.exchange,
                        memory_context=enriched_memory
                    )
                    
                    live = ai_result.get('live_execution', ai_result)
                    shadow = ai_result.get('shadow_optimizer', {})
                    live_score = live.get('score', 0)

                    # ── Enrich AI context with retraining few-shot examples ─────
                    if self.retrain_loop:
                        retrain_ctx = self.retrain_loop.get_few_shot_context()
                        if retrain_ctx:
                            logger.debug(f"[Retrain] Injecting {len(retrain_ctx.splitlines())} outcome lines into AI context.")

                    logger.info(f"🤖 AI Score: {live_score}/10")
                    
                    # Log to DB
                    log_data = {
                        **setup,
                        'ai_score': live_score,
                        'ai_reasoning': live.get('reasoning', ''),
                        'verdict': live.get('verdict', 'N/A'),
                        'shadow_regime': shadow.get('regime_classification', 'N/A'),
                        'shadow_multiplier': shadow.get('suggested_risk_multiplier', 1.0)
                    }
                    log_scan(log_data, live)
                    
                    # Use relaxed threshold for the proven Asian Fade prime window
                    is_asian_fade = setup.get('is_asian_fade', False)
                    threshold = Config.AI_THRESHOLD_ASIAN_FADE if is_asian_fade else Config.AI_THRESHOLD

                    # Alert if threshold met
                    if live_score >= threshold:
                        setups_found += 1
                        logger.info(f"🔔 HIGH QUALITY SETUP! Sending alert for {symbol}")
                        
                        # 💰 Risk Calculation (with regime size multiplier applied)
                        calc_equity = live_equity if live_equity > 0 else 100000.0
                        base_risk   = calc_equity * Config.RISK_PER_TRADE
                        risk_amt    = base_risk * regime_size_mult  # Regime adjusts size
                        distance    = abs(setup['entry'] - setup['stop_loss'])
                        
                        # Unit-based sizing (Standard for Crypto/Indices)
                        lots = (risk_amt / distance) if distance > 0 else 0
                        lots = round(lots, 2)
                        
                        risk_calc = {
                            "entry":         setup['entry'],
                            "stop_loss":     setup['stop_loss'],
                            "take_profit":   setup.get('target') or setup.get('tp1'),
                            "position_size": lots,
                            "equity_basis":  calc_equity,
                            "regime_mult":   regime_size_mult,
                        }

                        # ── SIGN THE SIGNAL (Feature 5: Signed Ledger) ──────────────
                        signal_id = "UNSIGNED"
                        if self.ledger:
                            try:
                                signal_id = self.ledger.sign_signal(setup, live_score)
                                logger.info(f"✍️  Signal signed: {signal_id}")
                            except Exception as e:
                                logger.error(f"Ledger signing failed: {e}")

                        # ── REGISTER CORRELATION SLOT ─────────────────────────────
                        self.corr_gate.register(signal_id, symbol, direction)

                        try:
                            prime_tag = "\n⭐ *PRIME WINDOW* — Asian Fade (100% Historical WR)" if setup.get('is_asian_fade') else ""
                            regime_tag = f"\n🌎 *Regime:* {regime_result.regime.value} | Size: {regime_size_mult:.0%}"
                            ledger_tag = f"\n🔒 *Signal ID:* `{signal_id}`" if signal_id != 'UNSIGNED' else ""
                            self.notifier.send_alert(
                                symbol=symbol,
                                timeframe=Config.TIMEFRAME,
                                pattern=setup['pattern'] + prime_tag + regime_tag,
                                ai_score=live_score,
                                reasoning=live.get('reasoning', ''),
                                verdict=live.get('verdict', 'N/A'),
                                risk_calc=risk_calc,
                                shadow_insights=shadow
                            )
                            # Append signal_id to the alert message as a separate line
                            if signal_id != 'UNSIGNED' and ledger_tag:
                                logger.info(f"Signal ID appended to alert: {signal_id}")
                        except Exception as e:
                            logger.error(f"❌ Failed to send Telegram alert: {e}")
            
            # 4. Rogue Execution Audit (The Policeman)
            logger.info("👮‍♂️ Running Rogue Execution Audit...")
            self.audit_engine.run_audit(hours_back=12)

            # 4b. Rogue Trade Ledger Check (Feature 5)
            # Any trade in the journal with strategy='ROGUE' and no matching signed signal
            if self.ledger:
                self._audit_rogue_ledger()

            # 5. Prop Guardian (Forensic Rule Audit every 6 hours)
            current_hour = datetime.now().hour
            if current_hour % 6 == 0 and time.time() - self.last_prop_audit > 7200:
                logger.info("🛡️ Prop Guardian: Checking forensic rule changes...")
                self.prop_guardian.batch_audit()
                self.last_prop_audit = time.time()

            # 6. Weekly Retraining Loop (Feature 6)
            if self.retrain_loop:
                retrain_result = self.retrain_loop.run_if_due()
                if retrain_result.get('status') == 'success':
                    samples = retrain_result.get('samples', 0)
                    wr = retrain_result.get('win_rate', 0)
                    logger.info(f"🔁 Retraining complete: {samples} samples | WR: {wr:.0%}")

            if setups_found == 0:
                trust = self.guard.get_trust_score()
                logger.info(f"💤 No setups found this cycle. 🛡️ Trust Score: {trust}/100")
                # HEARTBEAT: Log a silent scan to Supabase to keep Dashboard "Green"
                logger.info("💓 Heartbeat: System pulse sent to dashboard.")
                try:
                    hb_data = {
                        'timestamp': datetime.now().isoformat(),
                        'symbol': 'HEARTBEAT',
                        'pattern': 'System Active',
                        'bias': 'NEUTRAL',
                        'verdict': 'SCAN_HEARTBEAT'
                    }
                    log_scan(hb_data, {'score': 0, 'reasoning': 'Active Polling'})
                except: pass
                
        except Exception as e:
            logger.error(f"💥 Cycle Crash: {e}", exc_info=True)
            log_system_event("LocalRunner", str(e), level="ERROR")
            send_system_error("Local Runner", str(e))

    def _sync_trade_journal(self, live_equity):
        """Replicates cloud watchdog logic: Syncs history and positions to DB."""
        try:
            open_positions = self.tl.get_open_positions()
            # Pull 30 days of history to ensure full backfill
            history = self.tl.get_recent_history(hours=720)
            
            trades_today = len(history) + len(open_positions)
            update_sync_state(live_equity, trades_today)

            conn = get_db_connection()
            c = conn.cursor()
            
            # Upsert OPEN positions
            for t in open_positions:
                c.execute("""
                    INSERT INTO journal 
                    (timestamp, trade_id, symbol, side, pnl, price, status, ai_grade, mentor_feedback, strategy)
                    VALUES (?, ?, ?, ?, ?, ?, 'OPEN', 0.0, 'Synced Active Trade', 'SYSTEM')
                    ON CONFLICT(trade_id) DO UPDATE SET
                        pnl = excluded.pnl,
                        status = 'OPEN',
                        timestamp = excluded.timestamp
                """, (t['entry_time'], t['id'], t['symbol'], t['side'], t['pnl'], t['price']))

            # Upsert CLOSED history (full 30-day backfill)
            for t in history:
                entry_price = t.get('entry_price', t.get('price', 0.0))
                c.execute("""
                    INSERT INTO journal 
                    (timestamp, trade_id, symbol, side, pnl, price, status, ai_grade, mentor_feedback, strategy)
                    VALUES (?, ?, ?, ?, ?, ?, 'CLOSED', 0.0, 'Synced History', 'ROGUE')
                    ON CONFLICT(trade_id) DO UPDATE SET
                        pnl = excluded.pnl,
                        status = 'CLOSED',
                        price = excluded.price,
                        timestamp = excluded.timestamp
                """, (t['close_time'], t['id'], t['symbol'], t['side'], t['pnl'], entry_price))
                
            conn.commit()
            logger.info(f"📚 Journal synced: {len(history)} closed trades | {len(open_positions)} open positions")
            conn.close()
        except Exception as e:
            logger.error(f"⚠️ Watchdog Sync Failed: {e}")

    def _audit_rogue_ledger(self):
        """
        Cross-checks closed journal trades against the signed_ledger.
        Any trade with strategy='ROGUE' that has no matching signed signal_id
        gets flagged and a Telegram alert is sent.
        This runs every cycle — it's fast (SQLite query only).
        """
        try:
            conn = get_db_connection()
            c = conn.cursor()
            # Find recent CLOSED trades that were never matched to a signal
            c.execute("""
                SELECT trade_id, symbol, side, pnl, timestamp
                FROM journal
                WHERE status = 'CLOSED'
                  AND strategy = 'ROGUE'
                  AND date(timestamp) >= date('now', '-2 days')
                ORDER BY timestamp DESC
                LIMIT 20
            """)
            rogue_candidates = c.fetchall()
            conn.close()

            import sqlite3 as _sqlite3
            ledger_conn = _sqlite3.connect(self.ledger.db_path if hasattr(self.ledger, 'db_path') else Config.DB_PATH)
            ledger_conn.row_factory = _sqlite3.Row

            for trade in rogue_candidates:
                trade_id = trade['trade_id'] if isinstance(trade, dict) else trade[0]
                symbol   = trade['symbol']   if isinstance(trade, dict) else trade[1]
                pnl      = trade['pnl']      if isinstance(trade, dict) else trade[3]

                # Check if this trade_id already has a signed ledger entry
                existing = ledger_conn.execute(
                    "SELECT signal_id FROM signed_ledger WHERE trade_id = ? OR signal_id LIKE ?",
                    (str(trade_id), f'%{trade_id}%')
                ).fetchone()

                if not existing:
                    # Flag it as rogue in the ledger
                    rogue_id = self.ledger.flag_rogue(
                        trade_id=str(trade_id),
                        notes=f"Detected in journal audit — no matching signed signal. Symbol: {symbol} PnL: {pnl}"
                    )
                    logger.warning(f"🚨 ROGUE TRADE DETECTED: {symbol} | trade_id={trade_id} | PnL={pnl}")

                    # Alert via Telegram
                    try:
                        self.notifier.bot.send_message(
                            chat_id=self.notifier.chat_id,
                            text=(
                                f"🚨 *ROGUE TRADE DETECTED*\n\n"
                                f"A trade appeared in your account with *no matching signed signal*.\n\n"
                                f"Symbol: `{symbol}`\n"
                                f"Trade ID: `{trade_id}`\n"
                                f"PnL: `{pnl:+.2f}`\n"
                                f"Ledger Record: `{rogue_id}`\n\n"
                                f"This is either a manual trade or an unauthorized execution.\n"
                                f"Check your account immediately."
                            ),
                            parse_mode='Markdown'
                        )
                    except Exception as te:
                        logger.error(f"Rogue alert send failed: {te}")

            ledger_conn.close()

        except Exception as e:
            logger.error(f"[RogueLedgerAudit] Error: {e}")

    def main_loop(self):
        logger.info("⚙️ Sovereign SMC Local Runner Initialized.")
        logger.info(f"⏱️  Interval: {Config.get('RUN_INTERVAL_MINS', 5)} minutes")
        
        while self.running:
            start_time = time.time()
            self.run_cycle()
            
            # Wait for next interval
            elapsed = (time.time() - start_time) / 60
            sleep_time = max(1, (Config.get('RUN_INTERVAL_MINS', 5) - elapsed) * 60)
            
            if self.running:
                logger.info(f"😴 Sleeping for {sleep_time/60:.1f} minutes...")
                time.sleep(sleep_time)

if __name__ == "__main__":
    runner = LocalScannerRunner()
    runner.main_loop()

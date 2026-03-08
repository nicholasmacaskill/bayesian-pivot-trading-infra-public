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
from src.engines.psychology_engine import PsychologyEngine
from src.engines.biometric_engine  import BiometricEngine

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/local_runner.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
# Silence Noisy Third-Party Loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("google_genai").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

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
        
        # ── Biometrics & Psychology ───────────────────────────────────
        self.psychology    = PsychologyEngine()
        self.biometrics    = BiometricEngine(port=8080)
        self.biometrics.start_server()
        self.current_tilt_score = 1
        self.risk_multiplier   = 1.0
        self.last_psych_state  = {"tilt_score": 1, "sentiment": "Neutral", "reasoning": "Standard Start"}
        self.awaiting_psych_response = False
        self.last_psych_prompt_time = 0
        
        # Discretionary Alpha Interview State
        self.awaiting_alpha_interview = False
        self.interview_trade_id = None
        self.last_interview_prompt_time = 0
        self.processed_interviews = set() # Track IDs in-memory to avoid re-prompting
        # ───────────────────────────────────────────────────────────
        # ───────────────────────────────────────────────────────────

        # ── Sovereign Guard (Security Layer) ────────────────────────────────
        self.guard = GuardEngine(notifier=self.notifier)
        self.guard.start()
        logger.info("🛡️  Sovereign Guard active — securing your edge.")
        # ────────────────────────────────────────────────────────────────────
        
        self.last_market_pulse = 0
        self._cycle_count = 0
        self._last_signal_time = None

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

    def _print_cycle_header(self):
        """Prints a high-fidelity dashboard of the current system state."""
        self._cycle_count += 1
        now = datetime.now()
        cycle_time = now.strftime("%Y-%m-%d %H:%M:%S")
        
        # Determine Session
        hour = now.hour
        session = "NY/LONDON" if 12 <= hour < 20 else ("LONDON" if 7 <= hour < 12 else "ASIA")
        
        # Get Quartile
        q_data = self.scanner.get_session_quartile()
        q_label = f"{q_data['phase']}"
        
        # KZ Icons
        kz_icon = "🔵 KILLZONE ACTIVE" if self.scanner.is_killzone() else "⚪️ OUTSIDE KILLZONE"
        if self.scanner.is_asian_fade_window(): kz_icon = "⭐ PRIME WINDOW (FADE)"
        
        # Last Signal
        last_sig_str = "None"
        if self._last_signal_time:
            delta = (datetime.now(timezone.utc) if self._last_signal_time.tzinfo else datetime.now()) - self._last_signal_time
            last_sig_str = f"{int(delta.total_seconds() / 60)}m ago"
            
        # Mood, Trust & Health
        mood = "🪷 Flow" if self.risk_multiplier >= 1.0 else (f"⚠️ Stress ({self.current_tilt_score})" if self.risk_multiplier > 0 else "🛑 HARD GUARD")
        trust = self.guard.get_trust_score()
        
        # Performance Metrics from PropGuardian (calculated in run_cycle)
        perf = getattr(self, 'current_perf', {})
        dd_str = f"DD: {perf.get('daily_drawdown', 0):.1%} / {perf.get('total_drawdown', 0):.1%}"
        wr_rr = f"WR: {perf.get('win_rate', 0):.0%} | RR: {perf.get('avg_rr', 0):.1f}"

        # --- Active Positions ---
        active_positions = self.tl.get_open_positions()
        pos_count = len(active_positions)
        total_pnl = sum(p['pnl'] for p in active_positions)
        pnl_icon = "💰" if total_pnl >= 0 else "📉"

        logger.info(f"┌{'\u2500'*53}┐")
        logger.info(f"│  🚀 CYCLE #{self._cycle_count:<4}  {cycle_time:<22}│")
        logger.info(f"│  {session:<10} {kz_icon:<20} {dd_str:<20}│")
        logger.info(f"│  ⏱  {q_label:<15} {wr_rr:<18} Last: {last_sig_str:<7}│")
        logger.info(f"│  Mood: {mood:<20}  🛡️ Trust: {trust:<3}/100       │")
        
        if pos_count > 0:
            logger.info(f"├{'\u2500'*53}┤")
            logger.info(f"│  {pnl_icon} ACTIVE POSITIONS ({pos_count})       PnL: ${total_pnl:>+8.2f}  │")
            for p in active_positions:
                side_color = "🟢" if p['side'] == 'BUY' else "🔴"
                logger.info(f"│    {side_color} {p['symbol']:<10} @ ${p['price']:<9.2f} PnL: ${p['pnl']:>+7.2f}   │")
        
        logger.info(f"└{'\u2500'*53}┘")

    def run_cycle(self):
        logger.info("🚀 Starting SMC Alpha Scan Cycle...")
        self._print_cycle_header()
        self._send_pulse()
        try:
            # 1. Update Daily Start Equity (Anchor for drawdown)
            live_equity = self.tl.get_total_equity()
            if live_equity > 0:
                # Update daily anchor if not set
                state = get_db_connection().execute("SELECT value FROM sync_state WHERE key = 'daily_start_equity'").fetchone()
                if not state:
                    self.prop_guardian.update_daily_start(live_equity)
            
            # 2. Account Health & Accountability Audit
            logger.info("🛡️ Prop Guardian: Auditing Account Health...")
            health_report = self.prop_guardian.check_account_health(live_equity)
            self.current_perf = health_report
            
            # 3. Biometric & Psychology Audit (Interactive: Ask & Listen every 20 cycles)
            if self._cycle_count % 20 == 0 and not self.awaiting_psych_response:
                logger.info("🧠 Prompting User for Psychology Update...")
                self.notifier._send_message("🧠 *SOVEREIGN SENTIMENT:* How are you feeling right now? (Reply to update your risk profile)")
                self.awaiting_psych_response = True
                self.last_psych_prompt_time = int(time.time())
                
            if self.awaiting_psych_response:
                logger.info("🧠 Checking for User Sentiment Response...")
                user_response = self.notifier.get_latest_message(since_timestamp=self.last_psych_prompt_time)
                
                if user_response:
                    logger.info(f"🧠 Sentiment Received: {user_response['text']}")
                    physio_tilt = self.biometrics.calculate_physio_tilt()
                    psych_state = self.psychology.analyze_user_state(
                        current_text=user_response['text'], 
                        physio_tilt=physio_tilt
                    )
                    self.last_psych_state = psych_state
                    self.awaiting_psych_response = False
                    
                    # Feedback to User
                    mood = psych_state.get('sentiment', 'Unknown')
                    score = psych_state.get('tilt_score', 0)
                    mult = self.psychology.get_risk_multiplier(score)
                    self.notifier._send_message(f"✅ *SENTIMENT CAPTURED*\n• Mood: `{mood}`\n• Tilt Score: `{score}/10`\n• Risk Multiplier: `{mult}x`")
                else:
                    # Timeout after 15 minutes (5 cycles if interval=3m)
                    if time.time() - self.last_psych_prompt_time > 900:
                         logger.info("🧠 Psychology Prompt Timeout. Resetting...")
                         self.awaiting_psych_response = False

            self.current_tilt_score = self.last_psych_state.get('tilt_score', 1)

            # --- Alpha Interview Response Handler ---
            if self.awaiting_alpha_interview:
                logger.info(f"🎤 Checking for Alpha Interview Response (Trade: {self.interview_trade_id})...")
                user_response = self.notifier.get_latest_message(since_timestamp=self.last_interview_prompt_time)
                
                if user_response:
                    reasoning = user_response['text']
                    logger.info(f"🚀 Alpha Narrative Received: {reasoning}")
                    
                    # Update journal with human reasoning
                    from src.core.database import update_journal_notes
                    if update_journal_notes(self.interview_trade_id, reasoning):
                        self.notifier._send_message(f"✅ *ALPHA LOGGED*\nYour reasoning has been added to the SFT training context. The system is learning your edge.")
                    
                    self.awaiting_alpha_interview = False
                    self.processed_interviews.add(self.interview_trade_id)
                elif time.time() - self.last_interview_prompt_time > 1800: # 30 min timeout
                    logger.info("🎤 Alpha Interview Timeout.")
                    self.awaiting_alpha_interview = False
            
            # Combine Psychology and Prop Health for the final multiplier
            psych_mult = self.psychology.get_risk_multiplier(self.current_tilt_score)
            self.risk_multiplier = min(psych_mult, health_report['risk_multiplier'])
            
            if health_report['status'] != "HEALTHY":
                logger.warning(f"🛡️ PROP GUARD: {health_report['message']}")
            
            if self.risk_multiplier == 0:
                logger.error("🛑 HARD SHUTDOWN: Risk Shield Active. Skipping cycle.")
                return

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
            
            # 3. INTERMARKET CONTEXT BATCHING (Phase 3.5 Fix)
            # Fetch once per cycle to avoid getting IP-blocked by Yahoo Finance
            market_context = self.scanner.intermarket.get_market_context()
            logger.info("📡 Batched Intermarket Context retrieved.")
            
            for symbol in scan_list:
                logger.info(f"🔎 Scanning {symbol}...")
                
                # Scan Logic (SMC + Order Flow Fallback)
                # Pass batched context to avoid redundant network calls
                cached_ctx = {'intermarket': market_context} if market_context else None
                
                # Fetch Bias first for logging
                bias_score = self.scanner.get_detailed_bias(symbol, index_context=market_context)
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
                    result = self.scanner.scan_pattern(
                        symbol, 
                        timeframe=Config.TIMEFRAME,
                        cached_context=cached_ctx
                    )
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
                    
                    # PHASE 2: Inject regime into setup for ledger/retraining
                    setup['shadow_regime'] = regime_result.regime.value

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
                    security_status = self.guard.get_security_context()
                    # ────────────────────────────────────────────────────────

                    # AI Validation (Vision Proxy + RAG Active)
                    ai_result = validate_setup(
                        setup,
                        market_data,
                        whale_flow,
                        image_path=generated_chart,
                        df=df,
                        exchange=self.scanner.exchange,
                        memory_context=memory_context  # Reverted back to original memory context
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
                        from datetime import timezone
                        self._last_signal_time = datetime.now(timezone.utc)  # track for cycle header
                        logger.info(f"🔔 HIGH QUALITY SETUP [{symbol}] — Score: {live_score}/10")
                        
                        # 💰 Risk Calculation (with regime size multiplier applied)
                        calc_equity = live_equity if live_equity > 0 else 100000.0
                        base_risk   = calc_equity * Config.RISK_PER_TRADE
                        # Apply both Regime and Psychology risk multipliers
                        risk_amt    = base_risk * regime_size_mult * self.risk_multiplier
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
                            "psych_mult":    self.risk_multiplier,
                            "tilt_score":    self.current_tilt_score
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
                                shadow_insights=shadow,
                                security_status=security_status
                            )
                            # Append signal_id to the alert message as a separate line
                            if signal_id != 'UNSIGNED' and ledger_tag:
                                logger.info(f"Signal ID appended to alert: {signal_id}")
                        except Exception as e:
                            logger.error(f"❌ Failed to send Telegram alert: {e}")
            
            # 4. Rogue Execution Audit (The Policeman) - Run every 15 cycles
            if self._cycle_count % 15 == 0:
                logger.info("👮‍♂️ Running Rogue Execution Audit...")
                self.audit_engine.run_audit(hours_back=12)

            # 4b. Rogue Trade Ledger Check (Feature 5)
            # Any trade in the journal with strategy='ROGUE' and no matching signed signal
            if self.ledger:
                self._audit_rogue_ledger()

            # Prop Guardian: Forensic Check skipped (Now handled in cycle start via health audit)

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
                    # Get actual bias for heartbeat
                    btc_bias = self.scanner.get_detailed_bias("BTC/USD", index_context=market_context)
                    hb_data = {
                        'timestamp': datetime.now().isoformat(),
                        'symbol': 'HEARTBEAT',
                        'pattern': 'System Active',
                        'bias': btc_bias, # Use real bias
                        'verdict': 'SCAN_HEARTBEAT'
                    }
                    log_scan(hb_data, {'score': 0, 'reasoning': 'Active Polling'})

                    # ── MARKET PULSE: Send Visual Summary every 4 hours or on Strong Bias ──
                    if (time.time() - self.last_market_pulse > 14400) or ("STRONG" in btc_bias):
                        self._send_market_pulse("BTC/USD", btc_bias)
                        self.last_market_pulse = time.time()
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
                trade_id = t['id']
                pnl = t['pnl']
                
                c.execute("""
                    INSERT INTO journal 
                    (timestamp, trade_id, symbol, side, pnl, price, status, ai_grade, mentor_feedback, strategy)
                    VALUES (?, ?, ?, ?, ?, ?, 'CLOSED', 0.0, 'Synced History', 'ROGUE')
                    ON CONFLICT(trade_id) DO UPDATE SET
                        pnl = excluded.pnl,
                        status = 'CLOSED',
                        price = excluded.price,
                        timestamp = excluded.timestamp
                """, (t['close_time'], trade_id, t['symbol'], t['side'], pnl, entry_price))
                
                # ALPHA INTERVIEW TRIGGER: If newly closed, profitable, rogue, and not yet interviewed
                if pnl > 0 and trade_id not in self.processed_interviews and not self.awaiting_alpha_interview:
                    # Double check if we already have notes for this to avoid re-prompt on restart
                    c.execute("SELECT notes FROM journal WHERE trade_id = ?", (str(trade_id),))
                    row = c.fetchone()
                    if not row or not row[0]: # No notes yet
                         self._trigger_alpha_interview(t)
                
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

    def _trigger_alpha_interview(self, trade):
        """Sends the Alpha Interview prompt to Telegram."""
        try:
            trade_id = trade['id']
            symbol = trade['symbol']
            pnl = trade['pnl']
            
            logger.info(f"🚀 Triggering Alpha Interview for Trade {trade_id} ({symbol})")
            
            msg = (
                f"🚀 *ALPHA DETECTED: Profitable Discretionary Trade*\n\n"
                f"You just closed a win on `{symbol}` for `+${pnl:,.2f}`.\n\n"
                f"🎤 *THE INTERVIEW:* Why did you take this setup? What did the bot miss? (Reply with your reasoning for SFT learning)"
            )
            self.notifier._send_message(msg)
            
            self.awaiting_alpha_interview = True
            self.interview_trade_id = trade_id
            self.last_interview_prompt_time = int(time.time())
            self.processed_interviews.add(trade_id)
            
        except Exception as e:
            logger.error(f"Failed to trigger Alpha Interview: {e}")

    def _send_market_pulse(self, symbol, bias_str):
        """Sends a visual market pulse (Chart + Bias) to Telegram."""
        logger.info(f"📊 Sending Market Pulse for {symbol}...")
        try:
            df_4h = self.scanner.fetch_data(symbol, '4h', limit=100)
            if df_4h is None: return
            
            # Ensure charts directory exists
            os.makedirs(os.path.join("data", "charts"), exist_ok=True)
            chart_path = os.path.join("data", "charts", f"pulse_{int(time.time())}.png")
            
            from src.engines.visualizer import generate_bias_chart
            # Use generate_bias_chart for the visual pulse
            generate_bias_chart(df_4h, symbol, timeframe="4h", output_path=chart_path)
            
            caption = (
                f"📊 *SOVEREIGN MARKET PULSE*\n\n"
                f"🪙 *Symbol:* `{symbol}`\n"
                f"📉 *Current Bias:* `{bias_str}`\n"
                f"🛡️ *Trust Score:* `{self.guard.get_trust_score()}/100`"
            )
            
            if os.path.exists(chart_path):
                self.notifier.send_photo(chart_path, caption=caption)
            else:
                self.notifier._send_message(caption)
                
        except Exception as e:
            logger.error(f"Failed to send market pulse: {e}")

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

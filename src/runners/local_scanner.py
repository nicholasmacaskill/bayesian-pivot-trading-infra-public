import matplotlib
matplotlib.use('Agg')
import time
import requests
import logging
import signal
import sys
import os
import fcntl
from datetime import datetime, timezone, timedelta
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
from src.engines.local_llm_handler import LocalLLMHandler
# ── NEW: 5-Feature Suite ─────────────────────────────────────────────────────
from src.engines.correlation_gate import CorrelationGate
from src.engines.calendar_filter  import CalendarFilter
from src.engines.regime_filter     import RegimeFilter
from src.engines.trade_ledger      import TradeLedger
from src.engines.retraining_loop   import RetrainingLoop
from src.engines.psychology_engine import PsychologyEngine
from src.engines.biometric_engine  import BiometricEngine

# ── ICT Killzone Definitions (UTC hours) ─────────────────────────────────────
ICT_KILLZONES = [
    {'name': 'Asian',  'open': 0,  'close': 4},
    {'name': 'London', 'open': 7,  'close': 10},
    {'name': 'NY AM',  'open': 12, 'close': 15},
    {'name': 'NY PM',  'open': 18, 'close': 20},
]

def _get_active_killzone(utc_hour: int) -> dict | None:
    """Returns the active ICT killzone dict for the given UTC hour, or None."""
    for kz in ICT_KILLZONES:
        if kz['open'] <= utc_hour < kz['close']:
            return kz
    return None

def _is_presession_window(utc_hour: int, utc_minute: int) -> dict | None:
    """Returns killzone dict if we are within 15 minutes before its open, else None."""
    for kz in ICT_KILLZONES:
        pre_hour   = (kz['open'] - 1) % 24
        pre_minute = 45
        if utc_hour == pre_hour and utc_minute >= pre_minute:
            return kz
        if utc_hour == kz['open'] and utc_minute < 5:  # First 5 mins counts too
            return kz
    return None

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
        print("⚠️  Another instance of Bayesian Pivot is already running. Exiting.")
        sys.exit(0)

class LocalScannerRunner:
    def __init__(self):
        self.lock = check_single_instance()
        self.scanner = SMCScanner()
        self.sentiment_engine = SentimentEngine()
        self.tl = TradeLockerClient()
        self.audit_engine = ExecutionAuditEngine()
        self.prop_guardian = PropGuardian()
        self.retrain_loop = RetrainingLoop()
        
        self.running = True
        self._cycle_count = 0
        self._last_signal_time = None
        self.processed_interviews = set()
        self.scan_results = {} # Track per-symbol state for summary
        
        # State indicators
        self.risk_multiplier = 1.0
        self.last_prop_audit = 0
        self.last_market_pulse = 0
        
        # ── 5-Feature Suite ───────────────────────────────────────────
        self.notifier = TelegramNotifier()
        self.corr_gate    = CorrelationGate(
            max_per_direction=Config.get('CORRELATION_MAX_PER_DIRECTION', 1),
            expiry_hours=Config.get('CORRELATION_SLOT_EXPIRY_HRS', 4),
        )
        self.cal_filter   = CalendarFilter(
            blackout_minutes=Config.get('CALENDAR_BLACKOUT_MINUTES', 30),
        )
        self.regime_filter = RegimeFilter()
        self.ledger        = TradeLedger() if Config.get('LEDGER_ENABLED', True) else None
        
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
        self.last_command_time = int(time.time()) - 300 # Look back 5 mins on startup
        self.session_start_time = int(time.time())
        # ───────────────────────────────────────────────────────────
        # ───────────────────────────────────────────────────────────

        # ── Sovereign Guard (Security Layer) ────────────────────────────────
        self.guard = GuardEngine(notifier=self.notifier)
        self.guard.start()
        logger.info("🛡️  Sovereign Guard active — securing your edge.")
        # ────────────────────────────────────────────────────────────────────

        # ── Llama3 Local Fallback Validator ───────────────────────────────────
        self.local_llm = LocalLLMHandler(model="llama3")
        if self.local_llm.is_available():
            logger.info("🦙 Llama3 local validator: ONLINE")
        else:
            logger.warning("🦙 Llama3 local validator: OFFLINE (Ollama not running)")
        # ─────────────────────────────────────────────────────────────────────

        self.last_market_pulse = 0
        self._cycle_count = 0
        self._last_signal_time = None
        self._last_scan_results = [] # Track results for /scan report
        self._presession_scanned = set()  # Track which sessions have been pre-scanned this cycle

        # Shutdown handler
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

    def shutdown(self, signum, frame):
        logger.info("🛑 Shutdown signal received. Cleaning up...")
        self.running = False
        self.guard.stop()
        logger.info("🛡️  Sovereign Guard stopped.")

    def _handle_commands(self):
        """Listens for and executes Telegram commands (/status, /scan)."""
        msg = self.notifier.get_latest_message(since_timestamp=self.last_command_time)
        if not msg: 
            return
        
        self.last_command_time = msg['timestamp'] + 1
        text = msg['text'].strip().lower()
        logger.info(f"⌨️  User Command Detected: '{text}'")

        # Support both slash and non-slash versions
        if text in ['/status', 'status']:
            logger.info("🎰 Generating Bayesian Pivot Status Report...")
            self._send_status_report()
        elif text in ['/scan', 'scan']:
            logger.info("🔍 Generating Latest Bayesian Pivot Scan...")
            self._send_latest_scan_report()
        elif text in ['/guide', 'guide']:
            logger.info("📖 Sending Bayesian Pivot Command Guide...")
            self._send_command_guide()
        else:
            logger.debug(f"Ignored unknown message: {text}")

    def _send_status_report(self):
        """Sends a high-fidelity system status report via Telegram."""
        try:
            equity = self.tl.get_total_equity()
            
            # Daily Stats
            today = datetime.now().strftime('%Y-%m-%d')
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("SELECT COUNT(*), SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) FROM journal WHERE date(timestamp) = ?", (today,))
            trades_today, wins = c.fetchone()
            conn.close()
            
            btc_bias = self.scanner.get_detailed_bias("BTC/USD")
            
            msg = (
                f"📊 <b>BAYESIAN PIVOT STATUS</b>\n\n"
                f"💰 <b>Equity:</b> <code>${equity:,.2f}</code>\n"
                f"📈 <b>Trades Today:</b> <code>{trades_today or 0}</code> (Wins: <code>{wins or 0}</code>)\n"
                f"🧠 <b>Mood:</b> <code>{self.last_psych_state.get('sentiment', 'Neutral')}</code>\n"
                f"🛡️ <b>Risk Mult:</b> <code>{self.risk_multiplier:.2f}x</code> (Tilt: <code>{self.current_tilt_score}</code>)\n"
                f"✨ <b>Alpha Persistence:</b> <code>{getattr(self, 'alpha_mult', 1.0)}x</code>\n"
                f"🌎 <b>Market Pulse:</b> <code>{btc_bias}</code>\n\n"
                f"🕒 <i>Cycle #{self._cycle_count} Active</i>"
            )
            self.notifier._send_message(msg)
        except Exception as e:
            logger.error(f"Failed to generate status report: {e}")

    def _get_market_overview_ascii(self):
        """Generates a compact ASCII table of market states."""
        if not self.scan_results:
            return "No scan data available."
            
        lines = [
            "┌──────────┬─────────┬────────┬────────┐",
            "│ Symbol   │ Bias    │ Regime │ Hurst  │",
            "├──────────┼─────────┼────────┼────────┤"
        ]
        
        for symbol, data in self.scan_results.items():
            sym = symbol.split('/')[0]
            bias = str(data.get('bias', 'NEUTRAL'))[:7]
            regime = str(data.get('regime', 'CHOP'))[:6]
            hurst = f"{data.get('hurst', 0.5):.2f}"
            lines.append(f"│ {sym:<8} │ {bias:<7} │ {regime:<6} │ {hurst:<6} │")
            
        lines.append("└──────────┴─────────┴────────┴────────┘")
        return "\n".join(lines)

    def _send_latest_scan_report(self):
        """Sends a full Sovereign Market Briefing via Telegram on /scan."""
        try:
            # ── 1. Security & Session Header ─────────────────────────────────
            security   = self.guard.get_security_context()
            trust      = self.guard.get_trust_score()
            uptime     = str(timedelta(seconds=int(time.time() - self.session_start_time)))
            utc_now    = datetime.now(timezone.utc)
            active_kz  = _get_active_killzone(utc_now.hour)
            kz_name    = active_kz['name'] if active_kz else 'OFF-HOURS'
            quartile_d = self.scanner.get_session_quartile()
            sess_phase = quartile_d.get('phase', 'Unknown')

            health_report = getattr(self, 'current_perf', {})
            dd_pct = (health_report.get('daily_drawdown', 0.0) * 100) if health_report else 0.0
            integrity_badge = '⚠️ <b>[INTEGRITY: WARNING]</b>' if dd_pct >= 3.0 else '🛡️ <b>[INTEGRITY: SECURE]</b>'

            header = (
                f"🔍 <b>BAYESIAN PIVOT: SOVEREIGN BRIEFING</b>\n"
                f"{integrity_badge} | Trust: <code>{trust}/100</code>\n"
                f"📉 DD: <code>{dd_pct:.1f}% / 4.0%</code> | ⏱️ <b>{kz_name}</b> ({sess_phase})\n"
                f"🕒 Uptime: <code>{uptime}</code> | Cycle <code>#{self._cycle_count}</code>\n"
                f"🔐 <code>{security}</code>"
            )

            # ── 2. Account Balance ─────────────────────────────────────────────
            total_equity = self.tl.get_total_equity()

            # ── 3. Open Positions ──────────────────────────────────────────────
            open_positions = self.tl.get_open_positions()
            if open_positions:
                open_str = ''
                for p in open_positions:
                    side = 'BUY' if p.get('side','').upper() == 'BUY' else 'SELL'
                    pnl  = p.get('pnl', 0)
                    icon = '🟢' if pnl >= 0 else '🔴'
                    open_str += f"  {icon} <code>{p.get('symbol','N/A')}</code> {side} @ <code>{p.get('price',0):.4f}</code> → <code>{pnl:+.2f}</code>\n"
            else:
                open_str = '  <i>No open positions.</i>\n'

            # ── 4. Trade Stats (720h) ─────────────────────────────────────────
            history        = self.tl.get_recent_history(hours=720)
            history_sorted = sorted(history, key=lambda x: x.get('close_time', ''), reverse=True)
            winning  = [t for t in history if t.get('pnl', 0) > 0]
            losing   = [t for t in history if t.get('pnl', 0) < 0]
            total_cl = len(history)
            win_rate = (len(winning) / total_cl * 100) if total_cl > 0 else 0
            avg_win  = (sum(t['pnl'] for t in winning) / len(winning)) if winning else 0
            avg_loss = (abs(sum(t['pnl'] for t in losing)) / len(losing)) if losing else 1
            avg_rr   = (avg_win / avg_loss) if avg_loss > 0 else 0

            recent_str = ''
            for t in history_sorted[:5]:
                pnl  = t.get('pnl', 0)
                icon = '🟢' if pnl >= 0 else '🔴'
                ts   = t.get('close_time', '')[:10]
                recent_str += f"  {icon} <code>{t.get('symbol','N/A')}</code> {t.get('side','')} {ts} → <code>{pnl:+.2f}</code>\n"
            if not recent_str:
                recent_str = '  <i>No closed history found.</i>\n'

            # ── 5. Intermarket Confluence ───────────────────────────────────────
            market_context = getattr(self, '_last_market_context', {})
            if market_context:
                dxy = market_context.get('DXY', {})
                nq  = market_context.get('NQ', {})
                tnx = market_context.get('TNX', {})
                confluence_str = (
                    f"• <b>DXY:</b> <code>{dxy.get('trend','N/A')}</code> (<code>{dxy.get('change_5m',0):+.2f}%</code>)\n"
                    f"• <b>NQ:</b> <code>{nq.get('trend','N/A')}</code> (<code>{nq.get('change_5m',0):+.2f}%</code>)\n"
                    f"• <b>TNX:</b> <code>{tnx.get('trend','N/A')}</code> (<code>{tnx.get('change_5m',0):+.2f}%</code>)"
                )
            else:
                confluence_str = '<i>No intermarket data cached — run a cycle first.</i>'

            # ── 6. Alpha Persistence ───────────────────────────────────────────
            alpha_mult      = getattr(self, 'alpha_mult', 1.0)
            alpha_reasoning = getattr(self, 'alpha_reasoning', 'Initial baseline.')

            # ── 7. Market State Table (with Hurst strategy labels) ──────────────
            if self.scan_results:
                table_lines = [
                    '┌────────┬──────────┬────────┬──────┬─────────────┐',
                    '│ Symbol │ Bias     │ Regime │ Hurst│ Strategy    │',
                    '├────────┼──────────┼────────┼──────┼─────────────┤',
                ]
                for sym_full, data in self.scan_results.items():
                    sym    = sym_full.split('/')[0][:6]
                    bias   = str(data.get('bias', 'NEUTRAL'))[:8]
                    regime = str(data.get('regime', 'CHOP'))[:6]
                    h      = data.get('hurst', 0.5)
                    h_str  = f'{h:.2f}'
                    strat  = 'Turtle Soup' if h < 0.45 else ('Trend Align' if h > 0.55 else 'Structure  ')
                    table_lines.append(f'│ {sym:<6} │ {bias:<8} │ {regime:<6} │ {h_str:<4} │ {strat:<11} │')
                table_lines.append('└────────┴──────────┴────────┴──────┴─────────────┘')
                market_table = '\n'.join(table_lines)
            else:
                market_table = 'No scan data yet — trigger a cycle first.'

            # ── 8. Latest High-Score Setup (DB) ────────────────────────────────
            db_scan = ''
            try:
                conn = get_db_connection()
                row  = conn.execute(
                    "SELECT * FROM scans WHERE verdict != 'SCAN_HEARTBEAT' AND ai_score > 0 ORDER BY timestamp DESC LIMIT 1"
                ).fetchone()
                conn.close()
                if row:
                    try:
                        ts = datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00'))
                        if ts.tzinfo is None: ts = ts.replace(tzinfo=timezone.utc)
                    except: ts = datetime.now(timezone.utc)
                    mins_ago = int((datetime.now(timezone.utc) - ts).total_seconds() / 60)
                    db_scan = (
                        f"💎 <b>LATEST SETUP:</b> <code>{row['symbol']}</code> ({mins_ago}m ago)\n"
                        f"• Formation: <code>{row.get('formations') or row.get('pattern','N/A')}</code>"
                        f" | AI: <code>{row.get('ai_score','N/A')}/10</code>\n"
                        f"• Regime: <code>{row.get('shadow_regime','N/A')}</code>\n"
                        f"• <i>{row.get('ai_reasoning','No reasoning available.')}</i>\n"
                    )
                else:
                    db_scan = '<i>No high-conviction setups in database.</i>\n'
            except Exception as _db_err:
                db_scan = f'<i>DB query error: {_db_err}</i>\n'

            # ── ASSEMBLE FULL REPORT ───────────────────────────────────────────────
            msg = (
                f"{header}\n\n"

                f"💰 <b>Account</b>\n"
                f"• Total Equity: <code>${total_equity:,.2f}</code>\n\n"

                f"📂 <b>Open Positions ({len(open_positions)})</b>\n"
                f"{open_str}\n"

                f"📈 <b>Performance ({total_cl} trades)</b>\n"
                f"• Win Rate: <code>{win_rate:.1f}%</code> | Avg RR: <code>{avg_rr:.2f}</code>\n"
                f"• Avg Win: <code>${avg_win:+.2f}</code> | Avg Loss: <code>-${avg_loss:.2f}</code>\n\n"

                f"🕔 <b>Last 5 Closed</b>\n"
                f"{recent_str}\n"

                f"📐 <b>Confluence (Intermarket)</b>\n"
                f"{confluence_str}\n\n"

                f"✨ <b>Alpha Persistence:</b> <code>{alpha_mult:.2f}x</code> — <i>{alpha_reasoning}</i>\n\n"

                f"📊 <b>Market State</b> (Hurst-labeled)\n"
                f"<pre>{market_table}</pre>\n\n"

                f"{db_scan}"
            )

            self.notifier._send_message(msg)
        except Exception as e:
            logger.error(f"Failed to fetch enriched scan report: {e}", exc_info=True)

    def _send_command_guide(self):
        """Sends the pinned command guide to Telegram."""
        guide = (
            "🎯 <b>BAYESIAN PIVOT COMMAND GUIDE</b>\n\n"
            "Use these commands to interact with the system in real-time:\n\n"
            "📈 <b>/status</b> - Live equity, daily stats, and risk mood.\n"
            "🔍 <b>/scan</b> - Latest high-conviction setup detected.\n"
            "📖 <b>/guide</b> - View this command manual.\n\n"
            "🧠 <b>Interactive Features:</b>\n"
            "• <b>Sentiments:</b> Reply to hourly prompts with your mood to tune risk.\n"
            "• <b>Alpha Interviews:</b> When the bot asks 'Why?', provide your logic for SFT learning.\n\n"
            "<i>Pin this message for quick access.</i>"
        )
        self.notifier._send_message(guide)

    # PULSE PROTOCOL REMOVED (De-Modaled)

    def _get_recent_logs(self, n=15):
        """Reads the last n lines of the runner log and cleans them for Telegram."""
        try:
            log_path = "logs/local_runner.log"
            if not os.path.exists(log_path):
                return "No logs found."
            
            with open(log_path, "r") as f:
                lines = f.readlines()
            
            recent = lines[-n:]
            clean_lines = []
            for line in recent:
                # Remove common log metadata to save space: "2026-03-09 01:33:40,123 - Name - LEVEL - "
                parts = line.split(" - ")
                if len(parts) >= 3:
                    clean_lines.append(parts[-1].strip())
                else:
                    clean_lines.append(line.strip())
            
            return "\n".join(clean_lines)
        except Exception as e:
            return f"Error reading logs: {e}"

    def _get_dashboard_string(self):
        """Generates the same ASCII dashboard printed to terminal as a string."""
        now = datetime.now()
        cycle_time = now.strftime("%H:%M:%S")
        hour = now.hour
        session = "NY/LON" if 12 <= hour < 20 else ("LON" if 7 <= hour < 12 else "ASIA")
        
        q_data = self.scanner.get_session_quartile()
        kz_icon = "KZ: ON" if self.scanner.is_killzone() else "KZ: OFF"
        if self.scanner.is_asian_fade_window(): kz_icon = "⭐ FADE"
        
        perf = getattr(self, 'current_perf', {})
        dd_str = f"DD: {perf.get('daily_drawdown', 0):.1%} / {perf.get('total_drawdown', 0):.1%}"
        wr_rr = f"WR: {perf.get('win_rate', 0):.0%} | RR: {perf.get('avg_rr', 0):.1f}"
        mood = "FLOW" if self.risk_multiplier >= 1.0 else ("STRESS" if self.risk_multiplier > 0 else "HALT")
        
        active_positions = self.tl.get_open_positions()
        pos_count = len(active_positions)
        total_pnl = sum(p['pnl'] for p in active_positions)
        pnl_str = f"PnL: ${total_pnl:>+7.2f}"

        # Compact ASCII Box
        dash = [
            f"┌{'─'*38}┐",
            f"│ CYC #{self._cycle_count:<4} {cycle_time} {session:<6} {kz_icon:<8}│",
            f"│ {dd_str:<18} {wr_rr:<18} │",
            f"│ Mood: {mood:<10} {pnl_str:<18} │"
        ]
        
        if pos_count > 0:
            dash.append(f"├{'─'*38}┤")
            for p in active_positions[:2]: # Show max 2 to save space
                side = "L" if p['side'] == 'BUY' else "S"
                dash.append(f"│ {side} {p['symbol']:<10} @ {p['price']:<8.1f} PnL:${p['pnl']:>+6.1f} │")
        
        dash.append(f"└{'─'*38}┘")
        return "\n".join(dash)

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

        logger.info(f"└{'\u2500'*53}┘")

    def _print_market_overview(self):
        """Prints a compact table showing the scanned state of all symbols."""
        if not self.scan_results:
            return

        logger.info(f"┌{'\u2500'*61}┐")
        logger.info(f"│  MARKET STATE                                               │")
        logger.info( "├──────────┬─────────┬────────┬────────┬────────┬─────────────┤")
        logger.info(f"│ Symbol   │ Bias    │ Regime │ Hurst  │ SMT    │ Quartile    │")
        logger.info( "├──────────┼─────────┼────────┼────────┼────────┼─────────────┤")
        
        for symbol, data in self.scan_results.items():
            sym = symbol.split('/')[0]
            bias = str(data.get('bias', 'NEUTRAL'))[:7]
            regime = str(data.get('regime', 'CHOP'))[:6]
            hurst = f"{data.get('hurst', 0.5):.2f}"
            smt = f"{data.get('smt', 0.0):.2f}"
            quartile = str(data.get('quartile', 'N/A'))[:11]
            
            logger.info(f"│ {sym:<8} │ {bias:<7} │ {regime:<6} │ {hurst:<6} │ {smt:<6} │ {quartile:<11} │")
            
        logger.info( "└──────────┴─────────┴────────┴────────┴────────┴─────────────┘")

    def run_cycle(self):
        global log_scan
        logger.info("🚀 Starting Bayesian Pivot Scan Cycle...")
        self.scan_results = {} # Reset for this cycle
        self._handle_commands() # Listen for user requests
        self._print_cycle_header()
        
        try:
            # 1. Update Daily Start Equity (Anchor for drawdown)
            live_equity = self.tl.get_total_equity()
            if live_equity > 0:
                state = get_db_connection().execute("SELECT value FROM sync_state WHERE key = 'daily_start_equity'").fetchone()
                if not state:
                    self.prop_guardian.update_daily_start(live_equity)
            
            # 2. Account Health & Accountability Audit
            logger.info("🛡️ Prop Guardian: Auditing Account Health...")
            health_report = self.prop_guardian.check_account_health(live_equity)
            self.current_perf = health_report
            
            # 3. Biometric & Psychology Audit
            if self._cycle_count % 20 == 0 and not self.awaiting_psych_response:
                logger.info("🧠 Prompting User for Psychology Update...")
                self.notifier._send_message("🧠 *SOVEREIGN SENTIMENT:* How are you feeling right now? (Reply to update your risk profile)")
                self.awaiting_psych_response = True
                self.last_psych_prompt_time = int(time.time())
                
            if self.awaiting_psych_response:
                user_response = self.notifier.get_latest_message(since_timestamp=self.last_psych_prompt_time)
                if user_response:
                    physio_tilt = self.biometrics.calculate_physio_tilt()
                    psych_state = self.psychology.analyze_user_state(user_response['text'], physio_tilt=physio_tilt)
                    self.last_psych_state = psych_state
                    self.awaiting_psych_response = False
                    mood = psych_state.get('sentiment', 'Unknown')
                    score = psych_state.get('tilt_score', 0)
                    mult = self.psychology.get_risk_multiplier(score)
                    self.notifier._send_message(f"✅ *SENTIMENT CAPTURED*\n• Mood: `{mood}`\n• Tilt Score: `{score}/10`\n• Risk Multiplier: `{mult}x`")
                elif time.time() - self.last_psych_prompt_time > 900:
                    self.awaiting_psych_response = False

            self.current_tilt_score = self.last_psych_state.get('tilt_score', 1)
            
            # 3b. Alpha Persistence Audit
            self.alpha_mult = 1.0
            self.alpha_reasoning = "N/A"
            if self.retrain_loop:
                alpha_data = self.retrain_loop.get_alpha_persistence()
                self.alpha_mult = alpha_data['multiplier']
                self.alpha_reasoning = alpha_data['reasoning']

            # Combine Psychology and Prop Health
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
                 update_sync_state(live_equity, 0)
            
            # 2. Journal Watchdog
            self._sync_trade_journal(live_equity)
            
            scan_list = Config.SYMBOLS + Config.ALT_SYMBOLS
            setups_found = 0

            # 3. INTERMARKET CONTEXT BATCHING
            market_context = self.scanner.intermarket.get_market_context()
            self._last_market_context = market_context
            dxy_trend = market_context.get('DXY', {}).get('trend', 'N/A') if market_context else 'N/A'

            # 4. ICT SESSION CLASSIFICATION
            utc_now      = datetime.now(timezone.utc)
            utc_h, utc_m = utc_now.hour, utc_now.minute
            active_kz    = _get_active_killzone(utc_h)
            presession_kz = _is_presession_window(utc_h, utc_m)

            quartile_data = self.scanner.get_session_quartile()
            session_info  = {
                'name':  active_kz['name'] if active_kz else 'OFF-HOURS',
                'phase': quartile_data.get('phase', 'Unknown'),
            }

            # 5. PRE-SESSION GUARD SCAN (15 min before each killzone open, once per session)
            if presession_kz:
                scan_key = f"{presession_kz['name']}_{utc_now.date()}"
                if scan_key not in self._presession_scanned:
                    logger.info(f"🛡️ PRE-SESSION GUARD SCAN: {presession_kz['name']} opens in ~15 min")
                    # Run all lightweight scans synchronously (already in guard thread, just fetch result)
                    guard_ctx = self.guard.get_security_context()
                    self.notifier._send_message(
                        f"🛡️ <b>PRE-SESSION SWEEP: {presession_kz['name']}</b>\n"
                        f"Environment check 15 min before killzone open.\n"
                        f"• Result: <code>{guard_ctx}</code>"
                    )
                    self._presession_scanned.add(scan_key)
                    # Prune old keys to avoid unbounded growth
                    if len(self._presession_scanned) > 20:
                        self._presession_scanned.pop()

            for symbol in scan_list:
                cached_ctx = {'intermarket': market_context} if market_context else None

                # ── Bias Synthesis (Daily + 4H + DXY) ────────────────────────
                daily_bias = self.scanner.get_detailed_bias(symbol, index_context=market_context)
                htf_bias   = self.scanner.get_4h_bias(symbol)
                bias_score = daily_bias.split('(')[0].strip() if '(' in daily_bias else daily_bias
                bias_data  = {
                    'daily':     daily_bias,
                    'htf':       htf_bias,
                    'dxy_trend': dxy_trend,
                    'smt_score': f"{market_context.get('DXY', {}).get('change_5m', 0):+.2f}%" if market_context else 'N/A',
                }

                # ── Hurst Exponent + Strategy Label ───────────────────────────
                hurst_val = 0.5
                try:
                    df_tmp = self.scanner.fetch_data(symbol, Config.TIMEFRAME, limit=100)
                    if df_tmp is not None:
                        hurst_val = self.scanner.get_hurst_exponent(df_tmp['close'].values)
                except: pass

                if hurst_val < 0.45:
                    hunt_label = "Turtle Soup / Fade Search"
                elif hurst_val > 0.55:
                    hunt_label = "Trend Alignment / Displacement Search"
                else:
                    hunt_label = "Neutral / Structure Search"

                # ── HTF POI — Liquidity Gravity ───────────────────────────────
                liquidity_targets = None
                try:
                    pois = self.scanner.detect_htf_pois(symbol)
                    if pois:
                        # Prefer the closest unmitigated POI to current price
                        try:
                            df_1m  = self.scanner.fetch_data(symbol, '1m', limit=1)
                            price  = float(df_1m.iloc[-1]['close']) if df_1m is not None else 0
                        except: price = 0
                        nearest = min(pois, key=lambda p: abs(p['level'] - price)) if price else pois[0]
                        pip_size = 0.0001 if 'JPY' not in symbol else 0.01
                        dist_pips = abs(nearest['level'] - price) / pip_size if price else 0
                        liquidity_targets = {
                            'target_price': nearest['level'],
                            'target_type':  nearest['type'],
                            'distance_pips': dist_pips,
                        }
                except Exception as _poi_err:
                    logger.debug(f"HTF POI error for {symbol}: {_poi_err}")

                self.scan_results[symbol] = {
                    'bias':     bias_score,
                    'regime':   'CHOP',
                    'hurst':    hurst_val,
                    'smt':      market_context.get('DXY', {}).get('change_5m', 0) if market_context else 0.0,
                    'quartile': f"Q{quartile_data['num']}: {quartile_data['phase'][:7]}",
                }

                # Gates
                cal_safe, cal_reason = self.cal_filter.is_safe_to_trade(symbol)
                if not cal_safe: continue

                # Scan
                is_prime_window = self.scanner.is_asian_fade_window()
                result = None
                if is_prime_window:
                    result = self.scanner.scan_asian_fade(symbol)
                if not result:
                    result = self.scanner.scan_pattern(symbol, timeframe=Config.TIMEFRAME, cached_context=cached_ctx)
                if not result:
                    result = self.scanner.scan_order_flow(symbol, timeframe=Config.TIMEFRAME, cached_context=cached_ctx)

                if result:
                    setup, df = result
                    if not setup: continue

                    # Correlation & Regime
                    direction = setup.get('direction', setup.get('bias', ''))
                    corr_ok, _ = self.corr_gate.check(symbol, direction)
                    if not corr_ok: continue

                    df_1h = self.scanner.fetch_data(symbol, '1h', limit=200)
                    regime_result = self.regime_filter.classify(symbol, df_1h, df)
                    if not regime_result.allowed: continue

                    self.scan_results[symbol]['regime'] = regime_result.regime.value

                    # ── AI Validation (Cloud → Llama3 fallback) ───────────────
                    session_info_for_llm = session_info
                    try:
                        ai_result = validate_setup(
                            setup, self.sentiment_engine.get_market_sentiment(symbol),
                            self.sentiment_engine.get_whale_confluence(),
                            df=df, exchange=self.scanner.exchange, hurst_exponent=hurst_val
                        )
                        live = ai_result.get('live_execution', ai_result)
                        live_score = live.get('score', 0)
                    except Exception as _cloud_err:
                        logger.warning(f"☁️ Cloud AI failed for {symbol}: {_cloud_err} — trying Llama3...")
                        if self.local_llm.is_available():
                            try:
                                local_result = self.local_llm.score_setup(
                                    setup, market_context=market_context,
                                    hurst=hurst_val, session_info=session_info_for_llm
                                )
                                live = local_result
                                live_score = local_result.get('score', 0)
                                logger.info(f"🦙 Llama3 fallback score for {symbol}: {live_score}")
                            except Exception as _llm_err:
                                logger.error(f"🦙 Llama3 also failed: {_llm_err}")
                                continue
                        else:
                            continue

                    # Hurst-aware pattern label
                    base_pattern = setup.get('pattern', 'Unknown')
                    enriched_pattern = f"{hunt_label} — {base_pattern}"

                    # Threshold
                    is_asian_fade = setup.get('is_asian_fade', False)
                    threshold = Config.AI_THRESHOLD_ASIAN_FADE if is_asian_fade else Config.AI_THRESHOLD

                    if live_score >= threshold:
                        setups_found += 1
                        self._last_signal_time = datetime.now(timezone.utc)

                        # Sizing
                        calc_equity = live_equity if live_equity > 0 else 100000.0
                        base_risk   = calc_equity * Config.RISK_PER_TRADE
                        risk_amt    = base_risk * regime_result.suggested_size_mult * psych_mult * self.alpha_mult
                        lots = round(risk_amt / abs(setup['entry'] - setup['stop_loss']), 2) if abs(setup['entry'] - setup['stop_loss']) > 0 else 0

                        risk_calc = {
                            "entry": setup['entry'], "stop_loss": setup['stop_loss'],
                            "position_size": lots, "regime_mult": regime_result.suggested_size_mult,
                            "psych_mult": psych_mult, "alpha_mult": self.alpha_mult
                        }

                        signal_id = self.ledger.sign_signal(setup, live_score) if self.ledger else "UNSIGNED"
                        self.corr_gate.register(signal_id, symbol, direction)

                        self.notifier.send_alert(
                            symbol=symbol,
                            timeframe=Config.TIMEFRAME,
                            pattern=enriched_pattern,
                            ai_score=live_score,
                            reasoning=live.get('reasoning', ''),
                            risk_calc=risk_calc,
                            regime_result=regime_result,
                            health_report=health_report,
                            bias_data=bias_data,
                            liquidity_targets=liquidity_targets,
                            session_info=session_info,
                            security_status=self.guard.get_security_context(),
                        )
            
            if self._cycle_count % 15 == 0:
                self.audit_engine.run_audit(hours_back=12)
                if self.ledger: self._audit_rogue_ledger()

            if self.retrain_loop: self.retrain_loop.run_if_due()
            self._print_market_overview()

            if setups_found == 0:
                btc_bias = self.scanner.get_detailed_bias("BTC/USD", index_context=market_context)
                log_scan({'timestamp': datetime.now(timezone.utc).isoformat(), 'symbol': 'HEARTBEAT', 'pattern': 'System Active', 'bias': btc_bias, 'verdict': 'SCAN_HEARTBEAT'}, {'score': 0, 'reasoning': 'Active Polling'})
                if (time.time() - self.last_market_pulse > 14400) or ("STRONG" in btc_bias):
                    self._send_market_pulse("BTC/USD", btc_bias)
                    self.last_market_pulse = time.time()
                
        except Exception as e:
            logger.error(f"💥 Cycle Crash: {e}", exc_info=True)
            log_system_event("LocalRunner", str(e), level="ERROR")
            send_system_error("Local Runner", str(e))

    def _sync_trade_journal(self, live_equity):
        try:
            open_positions = self.tl.get_open_positions()
            history = self.tl.get_recent_history(hours=720)
            update_sync_state(live_equity, len(history) + len(open_positions))
            conn = get_db_connection()
            c = conn.cursor()
            for t in open_positions:
                c.execute("INSERT INTO journal (timestamp, trade_id, symbol, side, pnl, price, status, ai_grade, mentor_feedback, strategy) VALUES (?, ?, ?, ?, ?, ?, 'OPEN', 0.0, 'Synced Active Trade', 'SYSTEM') ON CONFLICT(trade_id) DO UPDATE SET pnl = excluded.pnl, status = 'OPEN'", (t['entry_time'], t['id'], t['symbol'], t['side'], t['pnl'], t['price']))
            for t in history:
                c.execute("INSERT INTO journal (timestamp, trade_id, symbol, side, pnl, price, status, ai_grade, mentor_feedback, strategy) VALUES (?, ?, ?, ?, ?, ?, 'CLOSED', 0.0, 'Synced History', 'ROGUE') ON CONFLICT(trade_id) DO UPDATE SET pnl = excluded.pnl, status = 'CLOSED'", (t['close_time'], t['id'], t['symbol'], t['side'], t['pnl'], t.get('price', 0)))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"⚠️ Watchdog Sync Failed: {e}")

    def _audit_rogue_ledger(self):
        try:
            conn = get_db_connection()
            rogues = conn.execute("SELECT trade_id, symbol, side, pnl FROM journal WHERE status = 'CLOSED' AND strategy = 'ROGUE' AND date(timestamp) >= date('now', '-2 days')").fetchall()
            conn.close()
            import sqlite3 as _sqlite3
            ledger_conn = _sqlite3.connect(self.ledger.db_path if hasattr(self.ledger, 'db_path') else Config.DB_PATH)
            for r in rogues:
                if not ledger_conn.execute("SELECT signal_id FROM signed_ledger WHERE trade_id = ?", (str(r[0]),)).fetchone():
                    self.ledger.flag_rogue(trade_id=str(r[0]), notes=f"Audit mismatch: {r[1]}")
                    self.notifier._send_message(f"🚨 <b>ROGUE TRADE DETECTED</b>\nSymbol: <code>{r[1]}</code>\nID: <code>{r[0]}</code>\nPnL: <code>{r[3]:+.2f}</code>")
            ledger_conn.close()
        except Exception as e:
            logger.error(f"[RogueLedgerAudit] Error: {e}")

    def _trigger_alpha_interview(self, trade):
        self.notifier._send_message(f"🚀 *ALPHA DETECTED: Profitable Discretionary Trade*\n`{trade['symbol']}` win: `+${trade['pnl']}`.\nWhy?")
        self.awaiting_alpha_interview = True
        self.interview_trade_id = trade['id']
        self.last_interview_prompt_time = int(time.time())

    def _send_market_pulse(self, symbol, bias_str):
        try:
            df_4h = self.scanner.fetch_data(symbol, '4h', limit=100)
            if df_4h is not None:
                os.makedirs("data/charts", exist_ok=True)
                path = f"data/charts/pulse_{int(time.time())}.png"
                from src.engines.visualizer import generate_bias_chart
                generate_bias_chart(df_4h, symbol, timeframe="4h", output_path=path)
                self.notifier.send_photo(path, caption=f"📊 *SOVEREIGN MARKET PULSE*\n`{symbol}` Bias: `{bias_str}`")
        except: pass

    def main_loop(self):
        logger.info("⚙️ Bayesian Pivot Local Runner Initialized.")
        while self.running:
            self.run_cycle()
            next_scan = time.time() + (Config.get('RUN_INTERVAL_MINS', 3) * 60)
            while time.time() < next_scan and self.running:
                self._handle_commands()
                time.sleep(5)

if __name__ == "__main__":
    runner = LocalScannerRunner()
    runner.main_loop()

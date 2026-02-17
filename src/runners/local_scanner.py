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
from src.engines.prop_guardian import PropGuardian
from src.core.database import init_db, log_scan, update_sync_state, log_system_event, get_db_connection, log_prop_audit
from src.clients.tl_client import TradeLockerClient
from src.clients.telegram_notifier import TelegramNotifier, send_alert, send_system_error
from src.engines.execution_audit import ExecutionAuditEngine

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("local_runner.log"),
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
        
        # Shutdown handler
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

    def shutdown(self, signum, frame):
        logger.info("🛑 Shutdown signal received. Cleaning up...")
        self.running = False

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

                result = self.scanner.scan_pattern(symbol, timeframe=Config.TIMEFRAME)
                if not result:
                    result = self.scanner.scan_order_flow(symbol, timeframe=Config.TIMEFRAME)
                
                if result:
                    setup, df = result
                    if not setup: continue
                    
                    logger.info(f"✅ Pattern Found: {setup.get('pattern')} on {symbol}")
                    
                    # Sentiment & Whales
                    market_data = self.sentiment_engine.get_market_sentiment(symbol)
                    whale_flow = self.sentiment_engine.get_whale_confluence()
                    
                    # AI Validation
                    ai_result = validate_setup(
                        setup, 
                        market_data, 
                        whale_flow, 
                        df=df,
                        exchange=self.scanner.exchange
                    )
                    
                    live = ai_result.get('live_execution', ai_result)
                    shadow = ai_result.get('shadow_optimizer', {})
                    live_score = live.get('score', 0)
                    
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
                    
                    # Alert if threshold met
                    if live_score >= Config.AI_THRESHOLD:
                        setups_found += 1
                        logger.info(f"🔔 HIGH QUALITY SETUP! Sending alert for {symbol}")
                        
                        # 💰 Risk Calculation (Optimized for Prop Mode)
                        # Default to $100k if sync failed (Safety fallback for offline mode)
                        calc_equity = live_equity if live_equity > 0 else 100000.0
                        risk_amt = calc_equity * Config.RISK_PER_TRADE
                        distance = abs(setup['entry'] - setup['stop_loss'])
                        
                        # Unit-based sizing (Standard for Crypto/Indices)
                        # Lots = (Risk $) / (Price Distance)
                        lots = (risk_amt / distance) if distance > 0 else 0
                        
                        # For BTC/ETH, we round to 2 decimal places (standard micro-lots)
                        lots = round(lots, 2)
                        
                        risk_calc = {
                            "entry": setup['entry'],
                            "stop_loss": setup['stop_loss'],
                            "take_profit": setup.get('target') or setup.get('tp1'), 
                            "position_size": lots,
                            "equity_basis": calc_equity
                        }
                        
                        try:
                            self.notifier.send_alert(
                                symbol=symbol,
                                timeframe=Config.TIMEFRAME,
                                pattern=setup['pattern'],
                                ai_score=live_score,
                                reasoning=live.get('reasoning', ''),
                                verdict=live.get('verdict', 'N/A'),
                                risk_calc=risk_calc,
                                shadow_insights=shadow
                            )
                        except Exception as e:
                            logger.error(f"❌ Failed to send Telegram alert: {e}")
            
            # 4. Rogue Execution Audit (The Policeman)
            logger.info("👮‍♂️ Running Rogue Execution Audit...")
            self.audit_engine.run_audit(hours_back=12)

            # 5. Prop Guardian (Forensic Rule Audit every 6 hours)
            current_hour = datetime.now().hour
            if current_hour % 6 == 0 and time.time() - self.last_prop_audit > 7200:
                logger.info("🛡️ Prop Guardian: Checking forensic rule changes...")
                self.prop_guardian.batch_audit()
                self.last_prop_audit = time.time()

            if setups_found == 0:
                logger.info("💤 No setups found this cycle.")
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
            history = self.tl.get_recent_history(hours=24)
            
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

            # Upsert CLOSED history
            for t in history:
                c.execute("""
                    INSERT INTO journal 
                    (timestamp, trade_id, symbol, side, pnl, price, status, ai_grade, mentor_feedback, strategy)
                    VALUES (?, ?, ?, ?, ?, ?, 'CLOSED', 0.0, 'Synced History', 'UNKNOWN')
                    ON CONFLICT(trade_id) DO UPDATE SET
                        pnl = excluded.pnl,
                        status = 'CLOSED',
                        price = excluded.price,
                        timestamp = excluded.timestamp
                """, (t['close_time'], t['id'], t['symbol'], t['side'], t['pnl'], t['price']))
                
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"⚠️ Watchdog Sync Failed: {e}")

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

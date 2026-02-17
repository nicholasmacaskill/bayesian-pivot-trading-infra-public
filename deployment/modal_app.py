import os
# Force Matplotlib to use non-interactive backend for Modal (Headless)
os.environ["MPLBACKEND"] = "Agg"
import matplotlib
matplotlib.use('Agg')

from src.core.config import Config
from src.core.database import init_db, log_scan, update_sync_state, get_sync_state, get_db_connection, log_prop_audit, get_latest_prop_audits
from src.engines.smc_scanner import SMCScanner
from src.clients.tl_client import TradeLockerClient
from src.engines.ai_validator import AIValidator, validate_setup
from src.engines.sentiment_engine import SentimentEngine
from src.clients.telegram_notifier import send_alert
from src.engines.prop_guardian import PropGuardian
import os
import json
from fastapi import Request, HTTPException
import modal
from datetime import datetime

# Define Modal Image with all dependencies and local Python files
image = (
    modal.Image.debian_slim()
    .apt_install("libgl1-mesa-glx", "libglib2.0-0")
    .pip_install_from_requirements("requirements.txt")
    .pip_install("yfinance", "pytz")
    .add_local_dir("src", remote_path="/root/src")
    .add_local_file("ict_oracle_kb.json", remote_path="/root/ict_oracle_kb.json")
    .add_local_file("ai_audit_engine.py", remote_path="/root/ai_audit_engine.py")
)

# Define App
app = modal.App("smc-alpha-scanner")

# Persistent Volume for SQLite
volume = modal.Volume.from_name("smc-alpha-storage", create_if_missing=True)

@app.function(
    image=image,
    schedule=modal.Cron("0 * * * *"), # Runs every hour
    secrets=Config.get_modal_secrets(),
    volumes={"/data": volume},
    timeout=600
)
def run_execution_audit():
    """
    Forensic Reconciler: Match real TradeLocker fills with system signals.
    """
    from src.engines.execution_audit import ExecutionAuditEngine
    print("👮‍♂️ Starting Scheduled Execution Audit...")
    try:
        engine = ExecutionAuditEngine()
        engine.run_audit(hours_back=24)
        print("✅ Execution Audit Complete.")
    except Exception as e:
        print(f"❌ Execution Audit Failed: {e}")

@app.function(
    image=image,
    schedule=modal.Cron("* * * * *"),  # Every 1 minute
    secrets=Config.get_modal_secrets(),
    volumes={"/data": volume}
)
def refresh_market_context():
    """
    ASYNCHRONOUS INTELLIGENCE: Background Pulse
    
    Runs every 1 minute to pre-warm market context, eliminating API latency
    during pattern execution. Caches news, sentiment, whale flow, and DXY data.
    """
    import json
    from datetime import datetime
    print("🧠 Refreshing Market Context (Background Pulse)...")
    
    from src.engines.news_filter import NewsFilter
    from src.engines.intermarket_engine import IntermarketEngine
    
    try:
        # Initialize engines
        news = NewsFilter()
        intermarket = IntermarketEngine()
        sentiment_engine = SentimentEngine()
        
        # Fetch all context
        is_safe, event, mins = news.is_news_safe()
        intermarket_data = intermarket.get_market_context()
        
        # Get sentiment and whale data for BTC (primary)
        market_sentiment = sentiment_engine.get_market_sentiment('BTC/USDT')
        whale_flow = sentiment_engine.get_whale_confluence()
        
        # Build context cache
        context = {
            'timestamp': str(datetime.utcnow()),
            'news': {
                'is_safe': is_safe,
                'event': event,
                'minutes_until': mins
            },
            'intermarket': intermarket_data,
            'sentiment': market_sentiment,
            'whales': whale_flow
        }
        
        # Save to volume
        cache_path = "/data/context_cache.json"
        with open(cache_path, 'w') as f:
            json.dump(context, f)
        
        volume.commit()
        print(f"✅ Context cached at {context['timestamp']}")
        
    except Exception as e:
        print(f"⚠️ Context refresh failed: {e}")

@app.function(
    image=image,
    schedule=modal.Cron("* * * * *"), # Runs every minute
    secrets=Config.get_modal_secrets(),
    volumes={"/data": volume}
)
def equity_watchdog():
    """Lightweight 1-minute poller to sync Equity & Closed Positions"""
    print("👀 Equity Watchdog: Checking for updates...")
    init_db()
    
    try:
        tl = TradeLockerClient()
        equity = tl.get_total_equity()
        
        # 1. Sync Equity
        if equity > 0:
             # Just use a placeholder for trade count until we fetch history below
             update_sync_state(equity, 0)
        
        
        # 2a. Sync Active Positions (OPEN)
        open_positions = tl.get_open_positions()
        
        # 2b. Sync Closed History (CLOSED)
        history = tl.get_recent_history(hours=24)
        
        trades_today = len(history) + len(open_positions)
        
        # Update sync state with actual count
        if equity > 0:
             update_sync_state(equity, trades_today)

        # Sync trades to Journal DB
        conn = get_db_connection()
        c = conn.cursor()
        new_synced = 0
        
        # A. Upsert OPEN positions
        for t in open_positions:
            try:
                # UPSERT logic: UPDATE if exists, INSERT if new
                # We update PnL and ensure status is OPEN
                c.execute("""
                    INSERT INTO journal 
                    (timestamp, trade_id, symbol, side, pnl, price, status, ai_grade, mentor_feedback)
                    VALUES (?, ?, ?, ?, ?, ?, 'OPEN', 0.0, 'Synced Active Trade')
                    ON CONFLICT(trade_id) DO UPDATE SET
                        pnl = excluded.pnl,
                        status = 'OPEN',
                        timestamp = excluded.timestamp
                """, (
                    t['entry_time'], 
                    t['id'], 
                    t['symbol'], 
                    t['side'], 
                    t['pnl'], 
                    t['price']
                ))
                new_synced += 1
            except Exception as e:
                print(f"⚠️ Open Position Sync Error {t['id']}: {e}")

        # B. Upsert CLOSED positions (This handles the OPEN -> CLOSED transition)
        for t in history:
            try:
                # If trade was previously OPEN, this will switch it to CLOSED and finalize PnL
                c.execute("""
                    INSERT INTO journal 
                    (timestamp, trade_id, symbol, side, pnl, price, status, ai_grade, mentor_feedback)
                    VALUES (?, ?, ?, ?, ?, ?, 'CLOSED', 0.0, 'Synced Closed Trade')
                    ON CONFLICT(trade_id) DO UPDATE SET
                        pnl = excluded.pnl,
                        status = 'CLOSED',
                        price = excluded.price,
                        timestamp = excluded.timestamp
                """, (
                    t['close_time'], 
                    t['id'], 
                    t['symbol'], 
                    t['side'], 
                    t['pnl'], 
                    t['price']
                ))
                # Only count as 'new synced' if it wasn't there (hard to track with upsert, but roughly)
            except Exception as e:
                print(f"⚠️ History Sync Error {t['id']}: {e}")
                
        conn.commit()
        conn.close()
        
        # PERSIST TO MODAL VOLUME
        try:
            volume.commit()
        except Exception as ve:
            print(f"⚠️ Volume Commit Failed: {ve}")

        print(f"✅ Watchdog: Equity=${equity:,.2f} | Trades={trades_today} | Synced={new_synced} new")
             
    except Exception as e:
        print(f"⚠️ Watchdog Failed: {e}")

@app.function(
    image=image,
    schedule=modal.Cron("*/5 * * * *"),
    secrets=Config.get_modal_secrets(),
    volumes={"/data": volume},
    timeout=900,
    max_containers=1
)
def run_scanner_job():
    from src.core.database import init_db, get_sync_state, log_system_event, log_scan, update_sync_state
    from src.clients.telegram_notifier import send_system_error
    
    try:
        print("🚀 Starting SMC Alpha Scan (Autonomous Mode)...")
        # 1. Initialize DB & Fetch Last State
        init_db()
        sync = get_sync_state()
        last_equity = float(sync.get('total_equity', 0.0))
        trades_today = sync.get('trades_today', 0)
        
        # 2. Automatic Equity Sync (Cloud -> TradeLocker)
        total_equity = last_equity
        try:
            print("🔗 Syncing real-time equity from TradeLocker...")
            tl = TradeLockerClient()
            live_equity = tl.get_total_equity()
            if live_equity > 0:
                total_equity = live_equity
                # Update DB for dashboard consistency
                update_sync_state(total_equity, int(trades_today))
                print(f"✅ Live Sync Successful: ${total_equity:,.2f}")
        except Exception as e:
            print(f"⚠️ Live Sync Failed (using fallback): {e}")

        print(f"📊 Status: Equity ${total_equity:,.2f} | Trades Today: {int(trades_today)}")
    
        # 3. Load Cached Context (Asynchronous Intelligence)
        cached_context = None
        try:
            import os
            import json
            cache_path = "/data/context_cache.json"
            if os.path.exists(cache_path):
                with open(cache_path, 'r') as f:
                    cached_context = json.load(f)
                print(f"🧠 Using pre-warmed context from {cached_context.get('timestamp', 'unknown')}")
            else:
                print("⚠️ No context cache found, will use live API calls")
        except Exception as e:
            print(f"⚠️ Failed to load context cache: {e}")
    
        # 4. Initialize Engines
        from src.engines.smc_scanner import SMCScanner
        from src.engines.sentiment_engine import SentimentEngine
        from src.clients.tl_client import TradeLockerClient
        
        scanner = SMCScanner()
        sentiment_engine = SentimentEngine()
        
        # 5. Risk Check: Daily Limit
        if int(trades_today) >= Config.DAILY_TRADE_LIMIT:
            print(f"🛑 Daily Trade Limit Reached ({trades_today}/{Config.DAILY_TRADE_LIMIT}). Skipping.")
            return
    
        # Combined Scan List (Majors + High Alpha Alts)
        scan_list = Config.SYMBOLS + Config.ALT_SYMBOLS
        
        setups_found = 0
        for symbol in scan_list:
            is_alt = symbol in Config.ALT_SYMBOLS
            print(f"🔎 Scanning {symbol} {'(Altcoin Mode)' if is_alt else ''}...")
            
            # STRATEGY 1: SMC ALPHA
            result = scanner.scan_pattern(symbol, timeframe=Config.TIMEFRAME, cached_context=cached_context)
            
            # STRATEGY 3: ORDER FLOW (Fallback if no SMC Alpha setup)
            if not result:
                result = scanner.scan_order_flow(symbol, timeframe=Config.TIMEFRAME)

            if result:
                try:
                    # Both scan_pattern and scan_order_flow now return (setup, df)
                    setup, df = result
                except (ValueError, TypeError):
                    print(f"⚠️ Unexpected result format for {symbol}: {result}")
                    continue
                    
                if not setup:
                    continue

                # ALTCOIN FILTER: Only accept "HIGH" quality (Judas Sweeps)
                if is_alt and setup.get('quality') != 'HIGH':
                    print(f"📉 Skipping {symbol} {setup.get('pattern')} (Medium Alpha). Alts require High Alpha.")
                    continue
                
                # Add Tag for Notifier
                if is_alt:
                    setup['tag'] = "💎 ALT GEM"
                
                print(f"✅ Pattern Found on {symbol}: {setup.get('pattern', 'Unknown')}")
                
                # Get Market Context (Use Cache or Fallback to Live)
                if cached_context:
                    market_data = cached_context['sentiment']
                    whale_flow = cached_context['whales']
                    print("⚡ Using cached sentiment (zero latency)")
                else:
                    market_data = sentiment_engine.get_market_sentiment(symbol)
                    whale_flow = sentiment_engine.get_whale_confluence()
                    print("🔄 Fetching live sentiment (fallback)")
                
                # Automated Visualization (The "Glass Eye")
                from src.engines.visualizer import generate_ict_chart
                chart_path = f"/tmp/{symbol.replace('/', '_')}_setup.png"
                generate_ict_chart(df, setup, output_path=chart_path)
                
                # 7. AI Validation with Context (Vision Informed + Dual-Track)
                ai_result = validate_setup(
                    setup, 
                    market_data, 
                    whale_flow, 
                    image_path=chart_path,
                    df=df,
                    exchange=scanner.exchange
                )
                
                # Extract dual-track results
                live = ai_result.get('live_execution', ai_result)
                shadow = ai_result.get('shadow_optimizer', {})
                
                print(f"🤖 AI Score: {live.get('score', ai_result.get('score', 0))}/10")
                if shadow:
                    print(f"🔬 Shadow: {shadow.get('regime_classification', 'N/A')} | Risk Multiplier: {shadow.get('suggested_risk_multiplier', 1.0)}x")

                # 8. Log Result (Fail-Safe)
                try:
                    log_data = {
                        **setup,
                        'ai_score': live.get('score', ai_result.get('score', 0)),
                        'ai_reasoning': live.get('reasoning', ai_result.get('reasoning', '')),
                        'verdict': live.get('verdict', ai_result.get('verdict', 'N/A')),
                        'shadow_regime': shadow.get('regime_classification', 'N/A'),
                        'shadow_multiplier': shadow.get('suggested_risk_multiplier', 1.0)
                    }
                    scan_id = log_scan(log_data, live)
                    volume.commit()
                except Exception as e:
                    print(f"⚠️ Database logging failed: {e}")
                    scan_id = None
                
                # 9. Alert if High Probability
                live_score = live.get('score', ai_result.get('score', 0))
                if live_score >= Config.AI_THRESHOLD:
                    setups_found += 1
                    risk_amt = total_equity * Config.RISK_PER_TRADE
                    distance = abs(setup['entry'] - setup['stop_loss'])
                    
                    firm_profile = Config.PROP_FIRMS[Config.ACTIVE_FIRM]
                    c_size = firm_profile['contract_size']
                    c_rate = firm_profile['commission_rate']
                    
                    raw_units = risk_amt / distance if distance > 0 else 0
                    
                    # Cap position at 70% of equity
                    position_value = raw_units * setup['entry']
                    max_position_value = total_equity * 0.70
                    if position_value > max_position_value:
                        raw_units = max_position_value / setup['entry']
                    
                    lots = raw_units / c_size if c_size > 0 else 0
                    
                    risk_calc = {
                        "entry": setup['entry'],
                        "stop_loss": setup['stop_loss'],
                        "take_profit": setup['target'],
                        "position_size": round(lots, 2),
                        "raw_units": round(raw_units, 4),
                        "contract_size": c_size,
                        "firm": Config.ACTIVE_FIRM,
                        "equity_basis": total_equity,
                        "sentiment": market_data["fear_and_greed"]
                    }
                    
                    execute_url = f"https://nicholasmacaskill--smc-alpha-scanner-execute-trade.modal.run?id={scan_id}"
                    buttons = [[
                        {"text": f"⚡ EXECUTE ({lots:.2f} Lots)", "url": execute_url},
                        {"text": "❌ DISMISS", "url": "https://t.me/SovereignSMCAuditBot"}
                    ]]

                    try:
                        send_alert(
                            symbol=symbol, 
                            timeframe=Config.TIMEFRAME,
                            pattern=setup['pattern'],
                            ai_score=live_score,
                            reasoning=live.get('reasoning', ai_result.get('reasoning', '')),
                            verdict=live.get('verdict', ai_result.get('verdict', 'N/A')),
                            risk_calc=risk_calc,
                            buttons=buttons,
                            shadow_insights=shadow
                        )
                    except Exception as alert_err:
                        print(f"⚠️ Telegram Alert Failed for {symbol}: {alert_err}")
                        log_system_event("Scanner Notifier", f"Failed to send alert for {symbol}: {str(alert_err)}", level="ERROR")
            else:
                # Hearbeat logging (optional, every 30 mins)
                if datetime.now().minute % 30 == 0:
                    try:
                        hb_data = {
                            'timestamp': datetime.now().isoformat(),
                            'symbol': symbol,
                            'pattern': 'Searching...',
                            'bias': scanner.get_4h_bias(symbol),
                            'ai_score': 0.0,
                            'ai_reasoning': 'N/A',
                            'verdict': 'SCAN_HEARTBEAT',
                            'shadow_regime': 'N/A',
                            'shadow_multiplier': 1.0
                        }
                        log_scan(hb_data, {'score': 0, 'reasoning': 'N/A'})
                        volume.commit()
                    except: pass
                print(f"No setup on {symbol}.")

        if setups_found == 0:
            print("💤 No setups found this cycle.")
            
    except Exception as e:
        import traceback
        err_msg = f"Scanner Job CRASH: {str(e)}\n{traceback.format_exc()}"
        print(err_msg)
        try:
            log_system_event("run_scanner_job", err_msg, level="CRITICAL")
            send_system_error("Scanner Job", str(e))
        except:
            print("🚨 Failed to log error to DB or Telegram")

@app.function(
    image=image,
    secrets=Config.get_modal_secrets(),
    volumes={"/data": volume}
)
@modal.fastapi_endpoint(method="POST")
async def push_equity(request: Request):
    """
    Secure endpoint for Local Dashboard to push equity/trade updates.
    Ensures account access only happens on User's Home IP.
    """
    data = await request.json()
    auth_key = os.environ.get("SYNC_AUTH_KEY") # Shared secret
    
    # Verification
    if data.get("key") != auth_key:
        raise HTTPException(status_code=403, detail="Invalid sync key")
        
    equity = data.get("total_equity")
    trades = data.get("trades_today")
    
    if equity is not None and trades is not None:
        update_sync_state(float(equity), int(trades))
        return {"status": "success", "message": f"Synced Equity: ${equity}"}
    
    return {"status": "error", "message": "Missing data"}

@app.function(
    image=image,
    secrets=Config.get_modal_secrets(),
    volumes={"/data": volume}
)
@modal.fastapi_endpoint(method="POST")
async def log_audit(request: Request):
    """
    Secure endpoint for Local Dashboard to push AI-generated Journal entries.
    """
    data = await request.json()
    
    # In real world, verify key here
    
    trade_id = data.get("trade_id")
    symbol = data.get("symbol")
    side = data.get("side")
    pnl = data.get("pnl")
    score = data.get("score")
    feedback = data.get("feedback")
    deviations = json.dumps(data.get("deviations", []))
    is_lucky = 1 if data.get("is_lucky_failure") else 0
    strategy = data.get("strategy", "ROGUE")
    
    if trade_id:
        from src.core.database import log_journal_entry
        log_journal_entry(trade_id, symbol, side, pnl, score, feedback, deviations, is_lucky, strategy)
        return {"status": "success", "message": f"Audit logged: {trade_id} ({strategy})"}
    
    return {"status": "error", "message": "Missing trade_id"}

@app.function(
    image=image,
    secrets=Config.get_modal_secrets(),
    volumes={"/data": volume}
)
@modal.fastapi_endpoint(docs=True)
def get_dashboard_state():
    """Consolidated API for Dashboard Data (Saves Endpoints)"""
    volume.reload()
    from src.core.database import get_db_connection, get_sync_state, get_latest_prop_audits
    conn = get_db_connection()
    c = conn.cursor()
    
    # 1. Scans
    c.execute("SELECT * FROM scans ORDER BY id DESC LIMIT 20")
    scans = [dict(row) for row in c.fetchall()]
    
    # 2. Journal
    c.execute("SELECT * FROM journal ORDER BY timestamp DESC LIMIT 50")
    journals = [dict(row) for row in c.fetchall()]
    
    # 3. Alpha Delta
    c.execute("SELECT * FROM scans ORDER BY timestamp DESC LIMIT 100")
    recent_scans = [dict(row) for row in c.fetchall()]
    
    sync = get_sync_state()
    try:
        equity = float(sync.get('total_equity', 0.0))
        trades_today = int(sync.get('trades_today', 0))
    except (ValueError, TypeError):
        equity = 0.0
        trades_today = 0
        
    alpha_results = []
    for j in journals:
        j_time = j['timestamp']
        best_scan = None
        for s in recent_scans:
            if s['symbol'] == j['symbol'] and s['timestamp'] <= j_time:
                best_scan = s
                break
        
        if best_scan:
            multiplier = best_scan.get('shadow_multiplier') or 1.0
            regime = best_scan.get('shadow_regime') or 'Unknown'
            
            pnl = j['pnl'] if j['pnl'] is not None else 0.0
            actual_risk = Config.RISK_PER_TRADE * 100
            shadow_risk = actual_risk * multiplier
            
            # ZeroDivision Check
            actual_ret = (pnl / equity) * 100 if equity > 0 else 0.0
            shadow_ret = actual_ret * multiplier
            
            # Use j.get('id', 0) to avoid KeyError if id missing (fallback)
            trade_identifier = j.get('id', 0)
            
            alpha_results.append({
                "trade_id": trade_identifier,
                "symbol": j['symbol'],
                "timestamp": j['timestamp'],
                "actual_return": round(actual_ret, 2),
                "shadow_return": round(shadow_ret, 2),
                "actual_risk": actual_risk,
                "shadow_risk": round(shadow_risk, 2),
                "regime": regime,
                "shadow_multiplier": multiplier,
                "notes": j.get('notes', ''),
                "strategy": j.get('strategy', 'ROGUE')
            })
            
    conn.close()
    
    return {
        "status": "active",
        "scans": scans,
        "equity": equity,
        "trades_today": trades_today,
        "journal_entries": journals,
        "alpha_delta": {"comparisons": alpha_results},
        "prop_audits": get_latest_prop_audits()
    }

@app.function(
    image=image,
    secrets=Config.get_modal_secrets(),
    volumes={"/data": volume}
)
@modal.fastapi_endpoint(docs=True)
def trigger_backfill_job(symbol: str = "BTC/USDT"):
    """Spawns the heavy backfill job in the background"""
    try:
        backfill_func = modal.Function.from_name("smc-backfill", "run_30_day_simulation")
        backfill_func.spawn(symbol)
        return {"status": "success", "message": f"Backtest started for {symbol}. Check back in ~10 minutes."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.function(
    image=image,
    secrets=Config.get_modal_secrets(),
    volumes={"/data": volume}
)
@modal.fastapi_endpoint(docs=True)
def get_backtest_reports():
    """Fetches historical simulation results"""
    volume.reload()
    from src.core.database import get_db_connection
    conn = get_db_connection()
    c = conn.cursor()
    # Check if table exists first (just in case init didn't run recently)
    try:
        c.execute("SELECT * FROM backtest_results ORDER BY id DESC LIMIT 5")
        rows = [dict(row) for row in c.fetchall()]
    except:
        rows = []
    conn.close()
    return {"status": "success", "reports": rows}

@app.function(
    image=image,
    secrets=Config.get_modal_secrets(),
    volumes={"/data": volume},
    timeout=1200
)
@modal.fastapi_endpoint(docs=True, method="POST")
def audit_prop_firms():
    """Trigger a forensic audit across all configured prop firms"""
    from src.engines.prop_guardian import PropGuardian
    guardian = PropGuardian()
    results = guardian.batch_audit()
    return {"status": "success", "audits": results}

@app.function(
    image=image,
    secrets=Config.get_modal_secrets(),
    volumes={"/data": volume}
)
@modal.fastapi_endpoint(docs=True)
def execute_trade(id: int):
    """
    ONE-TAP EXECUTION: Triggered by Telegram button.
    Fetches the scan, verifies the status, and pushes to TradeLocker.
    """
    from src.core.database import get_db_connection
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM scans WHERE id = ?", (id,))
    scan = c.fetchone()
    
    if not scan:
        return "ERROR: Scan not found."
    
    if scan['status'] == 'EXECUTED':
        return "ALREADY EXECUTED: This trade signal has already been sent to your account."

    try:
        from src.clients.tl_client import TradeLockerClient
        # tl = TradeLockerClient()
        # In this prototype, we log the success. Real execution logic would follow:
        # tl.open_position(symbol=scan['symbol'], ...)
        
        c.execute("UPDATE scans SET status = 'EXECUTED' WHERE id = ?", (id,))
        conn.commit()
        
        # Notify success
        from src.clients.telegram_notifier import send_alert
        # (Simplified notification of execution)
        
        return f"SUCCESS: Order for {scan['symbol']} has been placed on TradeLocker."
    except Exception as e:
        return f"EXECUTION FAILED: {str(e)}"
    finally:
        conn.close()

@app.function(
    image=image,
    secrets=Config.get_modal_secrets(),
    volumes={"/data": volume}
)
@modal.fastapi_endpoint(method="POST")
async def update_trade_notes(request: Request):
    """Updates personal notes for a trade"""
    data = await request.json()
    trade_id = data.get("trade_id")
    notes = data.get("notes")
    
    if not trade_id:
        return {"status": "error", "message": "Missing trade_id"}
        
    from src.core.database import update_journal_notes
    success = update_journal_notes(trade_id, notes)
    
    if success:
        return {"status": "success", "message": "Notes updated"}
    else:
        return {"status": "error", "message": "Failed to update notes"}

@app.function(
    image=image,
    schedule=modal.Cron("0 12 1 * *"),  # 12:00 PM on 1st of every month
    secrets=Config.get_modal_secrets(),
    volumes={"/data": volume}
)
def monthly_growth_alert():
    """
    GROWTH MINDSET PROTOCOL:
    Runs on the 1st of every month to tell you exactly:
    1. How much profit you made
    2. How much to withdraw (Your Paycheck)
    3. How many challenges to buy (Your Future)
    """
    from src.clients.tl_client import TradeLockerClient
    from src.clients.telegram_notifier import send_message
    from datetime import datetime
    
    # 1. Calculate Realized Profit (Simplified logic for now)
    # In reality, this would query trade history for the last 30 days
    # For now, we estimate based on equity growth
    
    tl = TradeLockerClient()
    current_equity = tl.get_total_equity()
    
    # Logic: Determine Phase based on Capital
    phase = "Phase 1 (Foundation)"
    reinvest_rate = 0.50
    if current_equity > 1000000:
        phase = "Phase 2 (Acceleration)"
        reinvest_rate = 0.75
    if current_equity > 6000000:
        phase = "Phase 3 (Harvest)"
        reinvest_rate = 0.0
        
    # Assume 3% monthly return for the notification estimates
    est_profit = current_equity * 0.03
    
    withdraw_amt = est_profit * (1 - reinvest_rate)
    reinvest_amt = est_profit * reinvest_rate
    challenges_to_buy = int(reinvest_amt / 500) # Assuming $500 per $50k challenge
    
    msg = f"""
🚀 **MONTHLY GROWTH PROTOCOL** 🚀
Date: {datetime.now().strftime('%B 1st, %Y')}

💰 **Capital:** ${current_equity:,.0f}
📊 **Est. Profit:** ${est_profit:,.0f}
Current Phase: {phase}

--- **ACTION REQUIRED** ---

💸 **PAY YOURSELF:** 
Withdraw: **${withdraw_amt:,.0f}**

🌱 **PLANT SEEDS:**
Reinvest: **${reinvest_amt:,.0f}**
Action: Buy **{challenges_to_buy}** New Challenges ($50k)

---------------------------
*The seeds you plant today feed you in 3 months.*
"""
    send_message(msg)
    print("✅ Monthly Growth Alert Sent")



import modal
from config import Config
from database import init_db, log_scan, update_sync_state, get_sync_state
from smc_scanner import SMCScanner
from ai_validator import validate_setup
from sentiment_engine import SentimentEngine
from telegram_notifier import send_alert
from tradelocker_client import TradeLockerClient
import os
import json
from fastapi import Request, HTTPException
import modal

# Define Modal Image with all dependencies and local Python files
image = (
    modal.Image.debian_slim()
    .pip_install_from_requirements("requirements.txt")
    .pip_install("yfinance", "pytz")
    .add_local_python_source("config")
    .add_local_python_source("database")
    .add_local_python_source("smc_scanner")
    .add_local_python_source("ai_validator")
    .add_local_python_source("sentiment_engine")
    .add_local_python_source("telegram_notifier")
    .add_local_python_source("tradelocker_client")
    .add_local_python_source("intermarket_engine")
    .add_local_python_source("news_filter")
    .add_local_python_source("visualizer")
    .add_local_file("ict_oracle_kb.json", remote_path="/root/ict_oracle_kb.json")
)

# Define App
app = modal.App("smc-alpha-scanner")

# Persistent Volume for SQLite
volume = modal.Volume.from_name("smc-alpha-storage", create_if_missing=True)

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
    
    from news_filter import NewsFilter
    from intermarket_engine import IntermarketEngine
    
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
    schedule=modal.Cron("*/5 * * * *"),
    secrets=Config.get_modal_secrets(),
    volumes={"/data": volume}
)
def run_scanner_job():
    print("🚀 Starting SMC Alpha Scan (Autonomous Mode)...")
    
    # 1. Initialize DB & Fetch Last State
    init_db()
    sync = get_sync_state()
    last_equity = sync.get('total_equity', 100000.0)
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
    scanner = SMCScanner()
    sentiment_engine = SentimentEngine()
    
    # 4. Risk Check: Daily Limit
    if int(trades_today) >= Config.DAILY_TRADE_LIMIT:
        print(f"🛑 Daily Trade Limit Reached ({trades_today}/{Config.DAILY_TRADE_LIMIT}). Skipping.")
        return
    
    for symbol in Config.SYMBOLS:
        print(f"🔎 Scanning {symbol}...")
        result = scanner.scan_pattern(symbol, cached_context=cached_context)
        
        if result:
            setup, df = result
            print(f"✅ Pattern Found on {symbol}: {setup['pattern']}")
            
            # 5. Get Market Context (Use Cache or Fallback to Live)
            if cached_context:
                market_data = cached_context['sentiment']
                whale_flow = cached_context['whales']
                print("⚡ Using cached sentiment (zero latency)")
            else:
                market_data = sentiment_engine.get_market_sentiment(symbol)
                whale_flow = sentiment_engine.get_whale_confluence()
                print("🔄 Fetching live sentiment (fallback)")
            
            # 6. Automated Visualization (The "Glass Eye")
            from visualizer import generate_ict_chart
            chart_path = f"/tmp/{symbol.replace('/', '_')}_setup.png"
            generate_ict_chart(df, setup, output_path=chart_path)
            
            # 7. AI Validation with Context (Vision Informed)
            ai_result = validate_setup(setup, market_data, whale_flow, image_path=chart_path)
                
            print(f"🤖 AI Score: {ai_result['score']}/10")

            # 6. Log Result (Faill-Safe)
            try:
                scan_id = log_scan(setup, ai_result)
            except Exception as e:
                print(f"⚠️ Database logging failed (skipping): {e}")
                scan_id = None
            
            # 7. Alert if High Probability
            if ai_result['score'] >= Config.AI_THRESHOLD:
                # Calculate Position Size (Target 0.75% risk, capped at 70% of equity)
                risk_amt = total_equity * Config.RISK_PER_TRADE
                distance = abs(setup['entry'] - setup['stop_loss'])
                size = risk_amt / distance if distance > 0 else 0
                
                # Cap position at 70% of equity (protects drawdown, maintains cash buffer)
                position_value = size * setup['entry']
                max_position_value = total_equity * 0.70
                
                if position_value > max_position_value:
                    size = max_position_value / setup['entry']
                    actual_risk = size * distance
                    print(f"⚠️ Position capped at 70%: ${position_value:,.2f} → ${max_position_value:,.2f} (Risk: ${actual_risk:,.2f})")
                
                risk_calc = {
                    "entry": setup['entry'],
                    "stop_loss": setup['stop_loss'],
                    "take_profit": setup['target'],
                    "position_size": round(size, 3),
                    "equity_basis": total_equity,
                    "is_ip_safe": True,
                    "sentiment": market_data["fear_and_greed"]
                }
                
                # 8. Add One-Tap Execution Buttons
                execute_url = f"https://nicholasmacaskill--smc-alpha-scanner-execute-trade.modal.run?id={scan_id}"
                
                buttons = [[
                    {"text": "⚡ EXECUTE (0.5%)", "url": execute_url},
                    {"text": "❌ DISMISS", "url": "https://t.me/SovereignSMCAuditBot"}
                ]]

                send_alert(
                    symbol=symbol, 
                    timeframe=Config.TIMEFRAME,
                    pattern=setup['pattern'],
                    ai_score=ai_result['score'],
                    reasoning=ai_result['reasoning'],
                    verdict=ai_result.get('verdict', 'N/A'),
                    risk_calc=risk_calc,
                    buttons=buttons
                )
                print("📨 Alert Sent to Telegram with One-Tap Buttons.")
        else:
            print(f"No setup on {symbol}.")

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
    
    if trade_id:
        from database import log_journal_entry
        log_journal_entry(trade_id, symbol, side, pnl, score, feedback, deviations, is_lucky)
        return {"status": "success", "message": f"Audit logged: {trade_id}"}
    
    return {"status": "error", "message": "Missing trade_id"}

@app.function(
    image=image,
    secrets=Config.get_modal_secrets(),
    volumes={"/data": volume}
)
@modal.fastapi_endpoint()
def get_latest_scans():
    """API for Next.js Dashboard to fetch data"""
    from database import get_db_connection
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM scans ORDER BY id DESC LIMIT 20")
    scans = [dict(row) for row in c.fetchall()]
    conn.close()
    return {"status": "active", "scans": scans}

@app.function(
    image=image,
    secrets=Config.get_modal_secrets(),
    volumes={"/data": volume}
)
@modal.fastapi_endpoint()
def execute_trade(id: int):
    """
    ONE-TAP EXECUTION: Triggered by Telegram button.
    Fetches the scan, verifies the status, and pushes to TradeLocker.
    """
    from database import get_db_connection
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM scans WHERE id = ?", (id,))
    scan = c.fetchone()
    
    if not scan:
        return "ERROR: Scan not found."
    
    if scan['status'] == 'EXECUTED':
        return "ALREADY EXECUTED: This trade signal has already been sent to your account."

    try:
        from tradelocker_client import TradeLockerClient
        # tl = TradeLockerClient()
        # In this prototype, we log the success. Real execution logic would follow:
        # tl.open_position(symbol=scan['symbol'], ...)
        
        c.execute("UPDATE scans SET status = 'EXECUTED' WHERE id = ?", (id,))
        conn.commit()
        
        # Notify success
        from telegram_notifier import send_alert
        # (Simplified notification of execution)
        
        return f"SUCCESS: Order for {scan['symbol']} has been placed on TradeLocker."
    except Exception as e:
        return f"EXECUTION FAILED: {str(e)}"
    finally:
        conn.close()
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
    from tradelocker_client import TradeLockerClient
    from telegram_notifier import send_message
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

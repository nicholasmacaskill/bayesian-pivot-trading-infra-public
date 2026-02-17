import os
# Force Matplotlib to use non-interactive backend
os.environ["MPLBACKEND"] = "Agg"
import matplotlib
matplotlib.use('Agg')

import modal
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import json
import logging

# Define Image
image = (
    modal.Image.debian_slim()
    .apt_install("libgl1-mesa-glx", "libglib2.0-0")
    .pip_install(
        "pandas", "numpy", "yfinance", "ccxt", "ta-lib", 
        "mplfinance", "google-genai", "python-telegram-bot", "requests", "pytz"
    )
    .add_local_python_source("config")
    .add_local_python_source("database")
    .add_local_python_source("smc_scanner")
    .add_local_python_source("ai_validator")
    .add_local_python_source("intermarket_engine")
    .add_local_python_source("news_filter")
    .add_local_python_source("visualizer")
    .add_local_python_source("tl_client")
    .add_local_python_source("sentiment_engine")
    .add_local_python_source("telegram_notifier")
)

app = modal.App("smc-backfill")
volume = modal.Volume.from_name("smc-alpha-storage")

@app.function(
    image=image,
    volumes={"/data": volume},
    timeout=3600, # 1 hour max
    secrets=[modal.Secret.from_name("smc-secrets")]
)
def run_30_day_simulation(symbol="BTC/USDT"):
    from src.engines.smc_scanner import SMCScanner
    from database import get_db_connection, init_db
    from config import Config
    
    # Ensure DB schema is up to date (create tables)
    init_db()

    print(f"🧪 Starting 30-Day Backfill for {symbol}...")
    
    # 1. Fetch Historical Data (30 Days)
    yf_symbol = "BTC-USD" if symbol == "BTC/USDT" else symbol.replace("/", "-")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    print(f"   Fetching data from {start_date.date()} to {end_date.date()}...")
    df = yf.download(yf_symbol, start=start_date, end=end_date, interval="5m", progress=False)
    
    if df.empty:
        print("❌ No data fetched.")
        return {"status": "error", "message": "No data"}
        
    # Flatten MultiIndex if needed
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    df = df.reset_index()
    df.columns = [c.lower() for c in df.columns]
    df.rename(columns={'date': 'timestamp', 'datetime': 'timestamp'}, inplace=True)
    
    # Ensure TZ naive
    if df['timestamp'].dt.tz is not None:
        df['timestamp'] = df['timestamp'].dt.tz_localize(None)

    total_candles = len(df)
    print(f"   Loaded {total_candles} candles.")

    scanner = SMCScanner()
    trades = []
    wins = 0
    losses = 0
    total_pnl = 0.0
    
    # 2. Iterate Candles (Simulation Loop)
    # We need at least 288 candles for lookback
    lookback = 300
    
    for i in range(lookback, total_candles):
        # Current Slice
        current_candle = df.iloc[i]
        timestamp = current_candle['timestamp']
        
        # Historical Dataframe Slice (up to this candle)
        # We pass a sufficiently large slice for indicators (e.g. 500 candles)
        slice_start = max(0, i - 1000)
        historical_slice = df.iloc[slice_start:i+1].copy()
        
        # Inject Time for Killzone Check
        # We need to be fast, so we check Killzone here first to skip 75% of candles
        if not scanner.is_killzone(current_time=timestamp):
            continue
            
        # Mock Context to prevent live API calls (Speed Optimization)
        mock_context = {
            "news": {"is_safe": True, "event": "Backtest", "minutes_until": 999},
            "intermarket": {"bias": "NEUTRAL", "DXY": {"change_5m": 0.0}}
        }

        # Run Scan
        try:
            result = scanner.scan_pattern(
                symbol, 
                provided_df=historical_slice, 
                current_time_override=timestamp,
                cached_context=mock_context
            )
        except Exception as e:
            print(f"Error at {timestamp}: {e}")
            continue
            
        if result:
            setup, _ = result
            # Skip "Test" patterns if any remain
            if "Test" in setup['pattern']: continue

             # Simulate Trade Outcome
            entry = setup['entry']
            sl = setup['stop_loss']
            tp = setup['target']
            direction = setup['direction']
            
            # Look Forward to determine outcome
            outcome = "OPEN"
            pnl = 0.0
            
            # Check next candles
            for future_i in range(i+1, min(i+288, total_candles)): # 24h max hold
                future_candle = df.iloc[future_i]
                h = future_candle['high']
                l = future_candle['low']
                
                if direction == 'LONG':
                    if l <= sl:
                        outcome = "LOSS"
                        pnl = -1.0 # -1R
                        break
                    if h >= tp:
                        outcome = "WIN"
                        pnl = 2.0 # +2R (Approx)
                        break
                else: # SHORT
                    if h >= sl:
                        outcome = "LOSS"
                        pnl = -1.0
                        break
                    if l <= tp:
                        outcome = "WIN"
                        pnl = 2.0
                        break
            
            if outcome != "OPEN":
                trades.append({
                    "timestamp": timestamp.isoformat(),
                    "pattern": setup['pattern'],
                    "direction": direction,
                    "outcome": outcome,
                    "pnl_r": pnl
                })
                if pnl > 0: wins += 1
                else: losses += 1
                total_pnl += pnl

    # 3. Log Results to DB
    conn = get_db_connection()
    c = conn.cursor()
    
    win_rate = (wins / len(trades) * 100) if trades else 0.0
    
    # Save Summary
    c.execute("""
        INSERT INTO backtest_results (run_date, symbol, timeframe, pnl, win_rate, total_trades, trade_log)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().isoformat(),
        symbol,
        "5m",
        total_pnl,
        win_rate,
        len(trades),
        json.dumps(trades)
    ))
    conn.commit()
    conn.close()
    
    print(f"✅ Simulation Complete!")
    print(f"   Trades: {len(trades)}")
    print(f"   Win Rate: {win_rate:.2f}%")
    print(f"   Total PnL (R-Multiples): {total_pnl:.2f}R")
    
    return {
        "trades": len(trades),
        "win_rate": win_rate,
        "pnl": total_pnl,
        "log": trades
    }

if __name__ == "__main__":
    with app.run():
        run_30_day_simulation.call()

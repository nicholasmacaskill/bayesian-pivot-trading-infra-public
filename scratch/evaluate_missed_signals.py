import sqlite3
import pandas as pd
import numpy as np
import ccxt
from datetime import datetime, timezone, timedelta
import time

def parse_db_time(time_str):
    if not time_str:
        return None
    try:
        # DB format is often ISO: 2026-03-10T06:57:58.883443
        # Remove Z and offset if present
        clean_str = time_str.split('+')[0].split('Z')[0]
        dt = datetime.fromisoformat(clean_str)
        return dt.replace(tzinfo=timezone.utc)
    except Exception as e:
        print(f"Error parsing time {time_str}: {e}")
        return None

def fetch_ccxt_data(symbol, start_dt, end_dt):
    exchange = ccxt.binance({'enableRateLimit': True})
    
    # Map symbols from USD to USDT
    ccxt_symbol = symbol.replace('/USD', '/USDT')
    print(f"📥 Fetching CCXT historical data for {ccxt_symbol} from {start_dt} to {end_dt}...")
    
    start_ts = int(start_dt.timestamp() * 1000)
    end_ts = int(end_dt.timestamp() * 1000)
    
    all_candles = []
    current_ts = start_ts
    
    while current_ts < end_ts:
        try:
            # fetch 1000 candles of 5m
            candles = exchange.fetch_ohlcv(ccxt_symbol, '5m', since=current_ts, limit=1000)
            if not candles:
                break
            all_candles.extend(candles)
            # check progress
            last_ts = candles[-1][0]
            if last_ts <= current_ts:
                break
            current_ts = last_ts + 1
            time.sleep(0.1) # Rate limit protection
        except Exception as e:
            print(f"Error fetching CCXT data: {e}")
            break
            
    if not all_candles:
        return pd.DataFrame()
        
    df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['parsed_time'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
    df = df.drop_duplicates(subset='parsed_time').reset_index(drop=True)
    print(f"✅ Fetched {len(df)} candles for {ccxt_symbol}")
    return df

def simulate_trade(signal, df_candles):
    entry = signal['entry_price']
    sl = signal['stop_loss']
    tp = signal['take_profit']
    direction = signal['direction'].upper() # 'LONG' or 'SHORT'
    sig_time = signal['parsed_time']
    
    # Filter candles to only those after the signal timestamp
    df_future = df_candles[df_candles['parsed_time'] >= sig_time].copy()
    if df_future.empty:
        return 'NO_DATA', 0, None, None
        
    filled = False
    fill_time = None
    outcome = None
    exit_time = None
    
    # Risk Reward calculations
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    r_multiple = reward / risk if risk > 0 else 0
    
    # Check if entry is valid
    if entry <= 0 or sl <= 0 or tp <= 0:
        return 'INVALID_PRICES', 0, None, None
        
    # We allow up to 48 hours for the trade to play out
    max_duration = timedelta(hours=48)
    
    for _, candle in df_future.iterrows():
        candle_time = candle['parsed_time']
        if candle_time - sig_time > max_duration:
            if filled:
                outcome = 'TIMEOUT_EXPIRED' # Trade timed out after 48h
            else:
                outcome = 'UNFILLED_TIMEOUT'
            exit_time = candle_time
            break
            
        candle_low = candle['low']
        candle_high = candle['high']
        
        if not filled:
            # Check for fill
            if direction == 'LONG' or 'BUY' in direction:
                if candle_low <= entry:
                    filled = True
                    fill_time = candle_time
            else: # SHORT
                if candle_high >= entry:
                    filled = True
                    fill_time = candle_time
                    
            # Check if target hit before fill (order cancelled)
            if not filled:
                if direction == 'LONG' or 'BUY' in direction:
                    if candle_high >= tp:
                        outcome = 'CANCELLED_TARGET_FIRST'
                        exit_time = candle_time
                        break
                else: # SHORT
                    if candle_low <= tp:
                        outcome = 'CANCELLED_TARGET_FIRST'
                        exit_time = candle_time
                        break
                        
        if filled:
            # Check for exits
            if direction == 'LONG' or 'BUY' in direction:
                # Conservative: check stop loss first in case both hit in same candle
                if candle_low <= sl:
                    outcome = 'LOSS'
                    exit_time = candle_time
                    break
                if candle_high >= tp:
                    outcome = 'WIN'
                    exit_time = candle_time
                    break
            else: # SHORT
                if candle_high >= sl:
                    outcome = 'LOSS'
                    exit_time = candle_time
                    break
                if candle_low <= tp:
                    outcome = 'WIN'
                    exit_time = candle_time
                    break
                    
    if outcome is None:
        if filled:
            outcome = 'OPEN'
        else:
            outcome = 'UNFILLED'
            
    # Calculate PnL (R-multiple)
    pnl_r = 0.0
    if outcome == 'WIN':
        pnl_r = r_multiple
    elif outcome == 'LOSS':
        pnl_r = -1.0
    elif outcome == 'TIMEOUT_EXPIRED':
        # Exit at close of timeout candle
        exit_price = df_future.iloc[-1]['close']
        if direction == 'LONG' or 'BUY' in direction:
            pnl_r = (exit_price - entry) / risk if risk > 0 else 0
        else:
            pnl_r = (entry - exit_price) / risk if risk > 0 else 0
            
    return outcome, pnl_r, fill_time, exit_time

def run_analysis():
    # Connect to local database
    conn = sqlite3.connect('data/smc_alpha.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Query all PENDING system signals in signed_ledger
    cursor.execute("""
        SELECT * FROM signed_ledger 
        WHERE outcome = 'PENDING' AND is_rogue = 0
        ORDER BY timestamp ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    signals = [dict(r) for r in rows]
    print(f"Total Pending Signals: {len(signals)}")
    if not signals:
        print("No pending signals to analyze.")
        return
        
    # Parse timestamps
    for s in signals:
        s['parsed_time'] = parse_db_time(s['timestamp'])
        
    # Filter out signals with invalid timestamps
    signals = [s for s in signals if s['parsed_time'] is not None]
    
    # Find overall min and max dates
    min_time = min(s['parsed_time'] for s in signals) - timedelta(days=1)
    max_time = max(s['parsed_time'] for s in signals) + timedelta(days=3)
    
    print(f"Signals Date Range: {min_time.isoformat()} to {max_time.isoformat()}")
    
    # Group signals by symbol to fetch price data in bulk
    unique_symbols = list(set(s['symbol'] for s in signals))
    print(f"Unique symbols in signals: {unique_symbols}")
    
    price_dfs = {}
    for sym in unique_symbols:
        # Skip HEARTBEAT or UNKNOWN symbols
        if sym in ['HEARTBEAT', 'UNKNOWN', '']:
            continue
        try:
            df_price = fetch_ccxt_data(sym, min_time, max_time)
            if not df_price.empty:
                price_dfs[sym] = df_price
        except Exception as e:
            print(f"Error fetching data for {sym}: {e}")
            
    # Simulate each signal
    results = []
    
    for s in signals:
        sym = s['symbol']
        if sym not in price_dfs:
            results.append({
                **s,
                'sim_outcome': 'NO_PRICE_DATA',
                'pnl_r': 0.0,
                'fill_time': None,
                'exit_time': None
            })
            continue
            
        outcome, pnl_r, fill_time, exit_time = simulate_trade(s, price_dfs[sym])
        results.append({
            **s,
            'sim_outcome': outcome,
            'pnl_r': pnl_r,
            'fill_time': fill_time,
            'exit_time': exit_time
        })
        
    df_results = pd.DataFrame(results)
    
    # Save results to a CSV/JSON file
    df_results.to_csv('results/missed_signals_analysis.csv', index=False)
    
    # Print Summary Metrics
    print("\n" + "="*50)
    print("📈 MISSED SIGNALS PERFORMANCE ANALYSIS")
    print("="*50)
    print(f"Total Signals Checked: {len(df_results)}")
    print(f"No Price Data:         {len(df_results[df_results['sim_outcome'] == 'NO_PRICE_DATA'])}")
    print(f"Invalid Prices:        {len(df_results[df_results['sim_outcome'] == 'INVALID_PRICES'])}")
    
    # Filter for active outcomes
    df_active = df_results[~df_results['sim_outcome'].isin(['NO_PRICE_DATA', 'INVALID_PRICES', 'UNFILLED_TIMEOUT', 'CANCELLED_TARGET_FIRST'])]
    print(f"Total Orders Placed (Limit): {len(df_results) - len(df_results[df_results['sim_outcome'] == 'NO_PRICE_DATA'])}")
    print(f"Cancelled (Target Hit First): {len(df_results[df_results['sim_outcome'] == 'CANCELLED_TARGET_FIRST'])}")
    print(f"Unfilled (Timed Out):        {len(df_results[df_results['sim_outcome'] == 'UNFILLED_TIMEOUT'])}")
    
    df_filled = df_results[df_results['sim_outcome'].isin(['WIN', 'LOSS', 'TIMEOUT_EXPIRED'])]
    print(f"Total Filled Trades:         {len(df_filled)}")
    
    if len(df_filled) > 0:
        wins = len(df_filled[df_filled['sim_outcome'] == 'WIN'])
        losses = len(df_filled[df_filled['sim_outcome'] == 'LOSS'])
        timeouts = len(df_filled[df_filled['sim_outcome'] == 'TIMEOUT_EXPIRED'])
        win_rate = (wins / len(df_filled)) * 100
        
        total_r = df_filled['pnl_r'].sum()
        avg_r = df_filled['pnl_r'].mean()
        
        print(f"  - Wins:                    {wins}")
        print(f"  - Losses:                  {losses}")
        print(f"  - Timeouts:                {timeouts}")
        print(f"  - Win Rate:                {win_rate:.2f}%")
        print(f"  - Total PnL (R-Multiple):  {total_r:+.2f}R")
        print(f"  - Average PnL per Trade:   {avg_r:+.2f}R")
        
        # Calculate PnL in USD assuming 1% risk per trade on a $100,000 account ($1000 risk per trade)
        risk_per_trade_usd = 1000
        total_pnl_usd = total_r * risk_per_trade_usd
        print(f"  - Simulated USD PnL:       ${total_pnl_usd:+,.2f} (assuming $1,000 risk per trade)")
        
        # Breakdown by Symbol
        print("\nBreakdown by Symbol (Filled Trades):")
        for sym in unique_symbols:
            df_sym = df_filled[df_filled['symbol'] == sym]
            if len(df_sym) > 0:
                sym_wins = len(df_sym[df_sym['sim_outcome'] == 'WIN'])
                sym_wr = (sym_wins / len(df_sym)) * 100
                sym_pnl = df_sym['pnl_r'].sum()
                print(f"  * {sym:<10}: {len(df_sym):>2} trades | Win Rate: {sym_wr:>5.1f}% | PnL: {sym_pnl:>+6.2f}R")
                
        # Breakdown by Pattern
        print("\nBreakdown by Pattern (Filled Trades):")
        unique_patterns = df_filled['pattern'].unique()
        for pat in unique_patterns:
            df_pat = df_filled[df_filled['pattern'] == pat]
            pat_wins = len(df_pat[df_pat['sim_outcome'] == 'WIN'])
            pat_wr = (pat_wins / len(df_pat)) * 100
            pat_pnl = df_pat['pnl_r'].sum()
            print(f"  * {pat:<40}: {len(df_pat):>2} trades | Win Rate: {pat_wr:>5.1f}% | PnL: {pat_pnl:>+6.2f}R")
            
    print("="*50 + "\n")

if __name__ == '__main__':
    run_analysis()

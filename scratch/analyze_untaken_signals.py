import os
import sys
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timezone, timedelta

# Add root directory to path
sys.path.append(os.getcwd())

# Load environment variables
if os.path.exists(".env.local"):
    with open(".env.local", "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

from src.core.supabase_client import SupabaseBridge
import ccxt

def fetch_all_candles(symbol, start_time, end_time):
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {'defaultType': 'future'}
    })
    binance_symbol = symbol.replace('/USD', '/USDT')
    since = int(start_time.replace(tzinfo=timezone.utc).timestamp() * 1000)
    end_ms = int(end_time.replace(tzinfo=timezone.utc).timestamp() * 1000)
    
    all_candles = []
    while since < end_ms:
        try:
            candles = exchange.fetch_ohlcv(binance_symbol, '5m', since, 1000)
            if not candles:
                break
            all_candles.extend(candles)
            since = candles[-1][0] + 1
            if len(candles) < 1000:
                break
        except Exception:
            break
    df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['parsed_time'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def analyze():
    # 1. Load executed trades from local SQLite journal to identify trade_ids or timestamps
    conn = sqlite3.connect('data/smc_alpha.db')
    df_journal = pd.read_sql_query("SELECT * FROM journal WHERE strategy='SYSTEM'", conn)
    conn.close()
    
    # Extract timestamps of executed trades (allowing +/- 2 hours for match matching)
    df_journal['datetime'] = df_journal['timestamp'].apply(lambda x: pd.to_datetime(int(x), unit='ms') if str(x).isdigit() else pd.to_datetime(str(x).replace("Z", "")))
    df_journal = df_journal.dropna(subset=['datetime'])
    executed_datetimes = df_journal['datetime'].tolist()
    
    # 2. Fetch all scans from Supabase
    sb = SupabaseBridge()
    limit = 1000
    offset = 0
    all_scans = []
    while True:
        res = sb.client.table("scans")\
            .select("*")\
            .or_("verdict.eq.ACCEPTED,and(verdict.eq.HARD_LOGIC_PASS,ai_score.gte.8.0)")\
            .order("timestamp", desc=False)\
            .range(offset, offset + limit - 1)\
            .execute()
        chunk = res.data
        if not chunk:
            break
        all_scans.extend(chunk)
        if len(chunk) < limit:
            break
        offset += limit
        
    df_scans = pd.DataFrame(all_scans)
    df_scans['parsed_time'] = pd.to_datetime(df_scans['timestamp'], format='ISO8601', utc=True).dt.tz_localize(None)
    df_scans = df_scans.dropna(subset=['parsed_time'])
    
    df_scans['entry'] = pd.to_numeric(df_scans['entry'], errors='coerce')
    df_scans['stop_loss'] = pd.to_numeric(df_scans['stop_loss'], errors='coerce')
    df_scans['target'] = pd.to_numeric(df_scans['target'], errors='coerce')
    df_scans = df_scans.sort_values(by='parsed_time')
    
    # Group duplicates (4 hours)
    distinct_signals = []
    for _, scan in df_scans.iterrows():
        is_duplicate = False
        scan_time = scan['parsed_time']
        scan_dir = str(scan.get('direction') or scan.get('bias') or '').upper()
        for logged in distinct_signals:
            if logged['symbol'] == scan['symbol'] and str(logged.get('direction') or logged.get('bias') or '').upper() == scan_dir:
                time_diff = (scan_time - logged['parsed_time']).total_seconds()
                if 0 <= time_diff < 14400: # 4 hours
                    is_duplicate = True
                    break
        if not is_duplicate:
            distinct_signals.append(scan.to_dict())
            
    df_distinct = pd.DataFrame(distinct_signals)
    
    # 3. Separate Untaken vs Taken Signals
    untaken_signals = []
    taken_signals = []
    
    for _, scan in df_distinct.iterrows():
        scan_time = scan['parsed_time']
        symbol = scan['symbol']
        
        # Check if this scan overlaps with any executed journal trade within 4 hours
        is_executed = False
        for exec_time in executed_datetimes:
            # Match if within 4 hours and asset is matching
            if abs((scan_time - exec_time).total_seconds()) < 14400 and (symbol in ['BTC/USD', 'BTC/USDT'] or symbol == 'BTC-Only'):
                is_executed = True
                break
                
        # If it's a BTC scan and was matching, or if we want to trace general executed
        # Note: executed journal trades only contains BTC system trades.
        # So SOL and ETH are inherently "untaken" because they were never executed on the account.
        if is_executed:
            taken_signals.append(scan.to_dict())
        else:
            untaken_signals.append(scan.to_dict())
            
    df_untaken = pd.DataFrame(untaken_signals)
    df_taken = pd.DataFrame(taken_signals)
    
    print(f"Total Vetted Grouped Setups: {len(df_distinct)}")
    print(f"Matches as 'Taken' (BTC Executed): {len(df_taken)}")
    print(f"Untaken Setups: {len(df_untaken)}")
    
    # Download candles
    start_date = df_distinct['parsed_time'].min() - timedelta(hours=1)
    end_date = df_distinct['parsed_time'].max() + timedelta(days=2)
    symbols = df_distinct['symbol'].unique()
    candle_dfs = {}
    for sym in symbols:
        df_c = fetch_all_candles(sym, start_date, end_date)
        candle_dfs[sym] = df_c
        
    # Resolve outcomes for UNTAKEN signals
    untaken_results = []
    for _, scan in df_untaken.iterrows():
        sym = scan['symbol']
        entry = scan.get('entry')
        stop = scan.get('stop_loss')
        target = scan.get('target')
        direction = str(scan.get('bias') or scan.get('direction') or 'Unknown')
        
        if sym not in candle_dfs:
            continue
        candles = candle_dfs[sym]
        scan_time = scan['parsed_time']
        
        has_null = pd.isna(entry) or pd.isna(stop) or pd.isna(target) or not entry or not stop or not target
        if has_null:
            past_candles = candles[candles['parsed_time'] <= scan_time]
            if len(past_candles) < 15:
                continue
            entry_candle = past_candles.iloc[-1]
            entry = float(entry_candle['close'])
            hl = past_candles['high'] - past_candles['low']
            hc = (past_candles['high'] - past_candles['close'].shift()).abs()
            lc = (past_candles['low'] - past_candles['close'].shift()).abs()
            tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]
            if pd.isna(atr) or atr <= 0:
                atr = entry * 0.005
            bias = str(scan.get('bias') or '').upper()
            direction_str = str(scan.get('direction') or '').upper()
            pattern_str = str(scan.get('pattern') or '').upper()
            is_short = 'SHORT' in direction_str or 'SELL' in direction_str or 'BEAR' in bias or 'SELL' in bias or 'SHORT' in bias or 'BEAR' in pattern_str or 'SHORT' in pattern_str
            stop_distance = atr * 2.0
            if is_short:
                stop = entry + stop_distance
                target = entry - (stop_distance * 3.0)
            else:
                stop = entry - stop_distance
                target = entry + (stop_distance * 3.0)
        else:
            entry = float(entry)
            stop = float(stop)
            target = float(target)
            is_short = 'SHORT' in direction.upper() or 'SELL' in direction.upper() or 'BEARISH' in direction.upper() or target < entry
            
        risk = abs(entry - stop)
        if risk == 0:
            continue
            
        future_candles = candles[candles['parsed_time'] >= scan_time]
        if future_candles.empty:
            continue
            
        fill_idx = None
        for idx, row in future_candles.head(288).iterrows():
            high = float(row['high'])
            low = float(row['low'])
            if low <= entry <= high:
                fill_idx = idx
                break
        if fill_idx is None:
            continue
            
        trade_candles = future_candles.loc[fill_idx:]
        resolved = False
        outcome = 'OPEN'
        r_multiple = 0.0
        
        for idx, row in trade_candles.head(288).iterrows():
            high = float(row['high'])
            low = float(row['low'])
            if is_short:
                if low <= target:
                    outcome = 'WIN'
                    r_multiple = abs(entry - target) / risk
                    resolved = True
                    break
                if high >= stop:
                    outcome = 'LOSS'
                    r_multiple = -1.0
                    resolved = True
                    break
            else:
                if high >= target:
                    outcome = 'WIN'
                    r_multiple = abs(target - entry) / risk
                    resolved = True
                    break
                if low <= stop:
                    outcome = 'LOSS'
                    r_multiple = -1.0
                    resolved = True
                    break
        if not resolved:
            last_row = trade_candles.head(288).iloc[-1]
            close_price = float(last_row['close'])
            if is_short:
                r_multiple = (entry - close_price) / risk
            else:
                r_multiple = (close_price - entry) / risk
            outcome = 'WIN' if r_multiple > 0 else 'LOSS'
            r_multiple = max(-1.0, min(r_multiple, (abs(entry - target) / risk)))
            resolved = True
            
        untaken_results.append({
            'symbol': sym,
            'direction': 'SHORT' if is_short else 'LONG',
            'outcome': outcome,
            'r_multiple': round(r_multiple, 2)
        })
        
    df_res = pd.DataFrame(untaken_results)
    
    print("\n=== UNTAKEN SIGNALS PERFORMANCE SUMMARY ===")
    print(f"Total Untaken Setups Resolved: {len(df_res)}")
    
    # Untaken overall win rate
    wins = len(df_res[df_res['outcome'] == 'WIN'])
    losses = len(df_res[df_res['outcome'] == 'LOSS'])
    wr = (wins / len(df_res)) * 100 if len(df_res) > 0 else 0
    net_r = df_res['r_multiple'].sum()
    print(f"Overall Untaken: {wr:.2f}% Win Rate | Net R-Multiple: {net_r:+.2f} R")
    
    # Untaken SHORTs
    shorts = df_res[df_res['direction'] == 'SHORT']
    s_wins = len(shorts[shorts['outcome'] == 'WIN'])
    s_losses = len(shorts[shorts['outcome'] == 'LOSS'])
    s_wr = (s_wins / len(shorts)) * 100 if len(shorts) > 0 else 0
    s_net_r = shorts['r_multiple'].sum()
    print(f"Untaken SHORTs Only: {s_wr:.2f}% Win Rate | Net R-Multiple: {s_net_r:+.2f} R ({len(shorts)} setups)")
    
    # Untaken LONGs
    longs = df_res[df_res['direction'] == 'LONG']
    l_wins = len(longs[longs['outcome'] == 'WIN'])
    l_losses = len(longs[longs['outcome'] == 'LOSS'])
    l_wr = (l_wins / len(longs)) * 100 if len(longs) > 0 else 0
    l_net_r = longs['r_multiple'].sum()
    print(f"Untaken LONGs Only: {l_wr:.2f}% Win Rate | Net R-Multiple: {l_net_r:+.2f} R ({len(longs)} setups)")
    
    # BTC Only Untaken
    btc_untaken = df_res[df_res['symbol'].isin(['BTC/USD', 'BTC/USDT'])]
    b_wins = len(btc_untaken[btc_untaken['outcome'] == 'WIN'])
    b_losses = len(btc_untaken[btc_untaken['outcome'] == 'LOSS'])
    b_wr = (b_wins / len(btc_untaken)) * 100 if len(btc_untaken) > 0 else 0
    b_net_r = btc_untaken['r_multiple'].sum()
    print(f"\nUntaken BTC-Only: {b_wr:.2f}% Win Rate | Net R-Multiple: {b_net_r:+.2f} R ({len(btc_untaken)} setups)")
    
    # BTC Untaken SHORTs
    btc_shorts = btc_untaken[btc_untaken['direction'] == 'SHORT']
    bs_wins = len(btc_shorts[btc_shorts['outcome'] == 'WIN'])
    bs_wr = (bs_wins / len(btc_shorts)) * 100 if len(btc_shorts) > 0 else 0
    bs_net_r = btc_shorts['r_multiple'].sum()
    print(f"Untaken BTC SHORTs Only: {bs_wr:.2f}% Win Rate | Net R-Multiple: {bs_net_r:+.2f} R ({len(btc_shorts)} setups)")

    # BTC Untaken LONGs
    btc_longs = btc_untaken[btc_untaken['direction'] == 'LONG']
    bl_wins = len(btc_longs[btc_longs['outcome'] == 'WIN'])
    bl_wr = (bl_wins / len(btc_longs)) * 100 if len(btc_longs) > 0 else 0
    bl_net_r = btc_longs['r_multiple'].sum()
    print(f"Untaken BTC LONGs Only: {bl_wr:.2f}% Win Rate | Net R-Multiple: {bl_net_r:+.2f} R ({len(btc_longs)} setups)")

if __name__ == '__main__':
    analyze()

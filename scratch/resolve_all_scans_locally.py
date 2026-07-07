import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

# Add root directory to path
sys.path.append(os.getcwd())

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
    print(f"   Downloading candles for {binance_symbol}...")
    
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
        except Exception as e:
            print(f"      Error fetching: {e}")
            break
            
    df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['parsed_time'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def resolve_all_scans():
    sb = SupabaseBridge()
    if not sb.client:
        print("❌ Supabase client failed to initialize.")
        return
        
    print("🔌 Fetching ALL vetted/accepted scans from Supabase...")
    limit = 1000
    offset = 0
    all_scans = []
    
    try:
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
            
        print(f"Retrieved {len(all_scans)} vetted scans from Supabase.")
        if not all_scans:
            return
            
        df_scans = pd.DataFrame(all_scans)
        print(f"   [Step 1] Total raw scans retrieved: {len(df_scans)}")
        
        df_scans['parsed_time'] = pd.to_datetime(df_scans['timestamp'], format='ISO8601', utc=True).dt.tz_localize(None)
        df_scans = df_scans.dropna(subset=['parsed_time'])
        print(f"   [Step 2] After dropping invalid timestamps: {len(df_scans)}")
        
        # Ensure values are numeric
        df_scans['entry'] = pd.to_numeric(df_scans['entry'], errors='coerce')
        df_scans['stop_loss'] = pd.to_numeric(df_scans['stop_loss'], errors='coerce')
        df_scans['target'] = pd.to_numeric(df_scans['target'], errors='coerce')
        
        # We do NOT drop null entry levels here anymore, we will infer them!
        print(f"   [Step 3] Proceeding with all scans (null levels will be inferred locally): {len(df_scans)}")
        
        df_scans = df_scans.sort_values(by='parsed_time')
        
        # Group duplicates within 4 hours
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
        print(f"Distinct Vetted Trade Opportunities (4H Grouped): {len(df_distinct)}")
        
        # Find time range for candles
        start_date = df_distinct['parsed_time'].min() - timedelta(hours=1)
        end_date = df_distinct['parsed_time'].max() + timedelta(days=2)
        print(f"Time range of scans: {start_date} to {end_date}")
        
        # Download candles
        symbols = df_distinct['symbol'].unique()
        candle_dfs = {}
        for sym in symbols:
            df_c = fetch_all_candles(sym, start_date, end_date)
            candle_dfs[sym] = df_c
            if not df_c.empty:
                print(f"   📊 Loaded {len(df_c)} candles for {sym} spanning {df_c['parsed_time'].min()} to {df_c['parsed_time'].max()}")
            else:
                print(f"   ⚠️ No candles loaded for {sym}")
            
        # Walk-forward resolution
        results = []
        null_levels_count = 0
        future_candles_empty_count = 0
        symbol_not_found_count = 0
        not_filled_count = 0
        
        print("\n=== Symbol distribution in distinct opportunities ===")
        print(df_distinct['symbol'].value_counts())
        
        for _, scan in df_distinct.iterrows():
            sym = scan['symbol']
            entry = scan.get('entry')
            stop = scan.get('stop_loss')
            target = scan.get('target')
            direction = str(scan.get('bias') or scan.get('direction') or 'Unknown')
            
            if sym not in candle_dfs:
                symbol_not_found_count += 1
                continue
                
            candles = candle_dfs[sym]
            scan_time = scan['parsed_time']
            
            # Check if levels are missing
            has_null = pd.isna(entry) or pd.isna(stop) or pd.isna(target) or not entry or not stop or not target
            
            if has_null:
                # Infer levels dynamically from past candles
                past_candles = candles[candles['parsed_time'] <= scan_time]
                if len(past_candles) < 15:
                    null_levels_count += 1
                    continue
                    
                entry_candle = past_candles.iloc[-1]
                entry = float(entry_candle['close'])
                
                # ATR(14)
                hl = past_candles['high'] - past_candles['low']
                hc = (past_candles['high'] - past_candles['close'].shift()).abs()
                lc = (past_candles['low'] - past_candles['close'].shift()).abs()
                tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
                atr = tr.rolling(14).mean().iloc[-1]
                
                if pd.isna(atr) or atr <= 0:
                    atr = entry * 0.005
                    
                # Determine direction
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
                null_levels_count += 1
                continue
            
            # Find the first candle after the scan
            future_candles = candles[candles['parsed_time'] >= scan_time]
            if future_candles.empty:
                future_candles_empty_count += 1
                continue
                
            # Check if limit order was filled within 24 hours (288 candles)
            fill_idx = None
            for idx, row in future_candles.head(288).iterrows():
                high = float(row['high'])
                low = float(row['low'])
                if low <= entry <= high:
                    fill_idx = idx
                    break
                    
            if fill_idx is None:
                # Limit order never filled
                not_filled_count += 1
                continue
                
            # Simulate from the fill candle onwards
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
                        
            # If still not resolved after 24 hours, close at market price (close of last candle)
            if not resolved:
                last_row = trade_candles.head(288).iloc[-1]
                close_price = float(last_row['close'])
                if is_short:
                    r_multiple = (entry - close_price) / risk
                else:
                    r_multiple = (close_price - entry) / risk
                outcome = 'WIN' if r_multiple > 0 else 'LOSS'
                r_multiple = max(-1.0, min(r_multiple, (abs(entry - target) / risk))) # Cap at stop/target
                resolved = True
                
            results.append({
                'timestamp': scan['timestamp'],
                'symbol': sym,
                'pattern': scan['pattern'],
                'direction': 'SHORT' if is_short else 'LONG',
                'outcome': outcome,
                'r_multiple': round(r_multiple, 2)
            })
                
        df_res = pd.DataFrame(results)
        print(f"\nSuccessfully resolved {len(df_res)} out of {len(df_distinct)} distinct setups.")
        print(f"   Skipped due to null levels (heartbeats/rejected scans): {null_levels_count}")
        print(f"   Skipped due to missing symbol candles: {symbol_not_found_count}")
        print(f"   Skipped due to empty future candles (new scans with no forward history yet): {future_candles_empty_count}")
        print(f"   Skipped due to limit order never filled: {not_filled_count}")
        
        if not df_res.empty:
            print("\n=== OVERALL FORWARD-TEST PERFORMANCE (3 MONTHS) ===")
            print(df_res['outcome'].value_counts())
            
            wins = len(df_res[df_res['outcome'] == 'WIN'])
            losses = len(df_res[df_res['outcome'] == 'LOSS'])
            total = len(df_res)
            win_rate = (wins / total) * 100
            
            total_r = df_res['r_multiple'].sum()
            profit_factor = abs(df_res[df_res['r_multiple'] > 0]['r_multiple'].sum() / df_res[df_res['r_multiple'] < 0]['r_multiple'].sum()) if losses > 0 else float('inf')
            
            print(f"\nWin Rate:       {win_rate:.2f}% ({wins} W / {losses} L)")
            print(f"Profit Factor:  {profit_factor:.2f}")
            print(f"Total Net R:    {total_r:.2f} R")
            print(f"Avg R per Trade: {df_res['r_multiple'].mean():.2f} R")
            
            print(f"\n💵 Projected PnL at $200 risk per trade: ${total_r * 200:,.2f}")
            print(f"💵 Projected PnL at $500 risk per trade: ${total_r * 500:,.2f}")
            
            # Print performance by asset
            print("\n=== Performance by Asset ===")
            for sym in df_res['symbol'].unique():
                sym_df = df_res[df_res['symbol'] == sym]
                s_wins = len(sym_df[sym_df['outcome'] == 'WIN'])
                s_total = len(sym_df)
                s_wr = (s_wins / s_total) * 100 if s_total > 0 else 0
                s_r = sym_df['r_multiple'].sum()
                print(f"   {sym}: {s_total} trades | Win Rate: {s_wr:.2f}% | Net R: {s_r:.2f} R")
                
                # Print direction breakdown
                for dir_name in ['LONG', 'SHORT']:
                    dir_df = sym_df[sym_df['direction'] == dir_name]
                    if not dir_df.empty:
                        d_wins = len(dir_df[dir_df['outcome'] == 'WIN'])
                        d_total = len(dir_df)
                        d_wr = (d_wins / d_total) * 100
                        d_r = dir_df['r_multiple'].sum()
                        print(f"      ↳ {dir_name}: {d_total} trades | WR: {d_wr:.2f}% | Net R: {d_r:.2f} R")
                
            # Print performance by pattern
            print("\n=== Performance by Pattern ===")
            for pat in df_res['pattern'].unique():
                pat_df = df_res[df_res['pattern'] == pat]
                p_wins = len(pat_df[pat_df['outcome'] == 'WIN'])
                p_total = len(pat_df)
                p_wr = (p_wins / p_total) * 100 if p_total > 0 else 0
                p_r = pat_df['r_multiple'].sum()
                print(f"   {pat}: {p_total} trades | Win Rate: {p_wr:.2f}% | Net R: {p_r:.2f} R")
                
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    resolve_all_scans()

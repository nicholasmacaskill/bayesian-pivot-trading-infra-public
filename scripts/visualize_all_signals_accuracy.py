import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timezone, timedelta
import sqlite3

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

plt.style.use('dark_background')
accent_color = '#00ffcc'       # Sovereign Teal
secondary_color = '#ff3366'    # Risk Red
highlight_color = '#ffcc00'    # Outlier Gold
muted_gray = '#4f5e71'         # Grid Muted Gray
system_color = '#3399ff'       # System Blue

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

def run_analysis():
    sb = SupabaseBridge()
    if not sb.client:
        print("❌ Supabase client failed to initialize.")
        return
        
    print("🔌 Fetching ALL vetted/accepted scans from Supabase...")
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
        
    print(f"Retrieved {len(all_scans)} vetted scans from Supabase.")
    if not all_scans:
        return
        
    df_scans = pd.DataFrame(all_scans)
    df_scans['parsed_time'] = pd.to_datetime(df_scans['timestamp'], format='ISO8601', utc=True).dt.tz_localize(None)
    df_scans = df_scans.dropna(subset=['parsed_time'])
    
    # Ensure values are numeric
    df_scans['entry'] = pd.to_numeric(df_scans['entry'], errors='coerce')
    df_scans['stop_loss'] = pd.to_numeric(df_scans['stop_loss'], errors='coerce')
    df_scans['target'] = pd.to_numeric(df_scans['target'], errors='coerce')
    
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
    
    # Download candles
    symbols = df_distinct['symbol'].unique()
    candle_dfs = {}
    for sym in symbols:
        df_c = fetch_all_candles(sym, start_date, end_date)
        candle_dfs[sym] = df_c
        
    # Walk-forward resolution
    results = []
    
    for _, scan in df_distinct.iterrows():
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
            # Infer levels
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
            
        results.append({
            'date': scan_time.date(),
            'timestamp': scan['timestamp'],
            'symbol': sym,
            'pattern': scan['pattern'],
            'direction': 'SHORT' if is_short else 'LONG',
            'outcome': outcome,
            'r_multiple': round(r_multiple, 2)
        })
            
    df_res = pd.DataFrame(results)
    
    # ------------------- DATA ANALYSIS & STATS -------------------
    # Load actual executed system trades from SQLite
    conn = sqlite3.connect('data/smc_alpha.db')
    df_journal = pd.read_sql_query("SELECT * FROM journal WHERE strategy='SYSTEM'", conn)
    conn.close()
    
    # Format executed trades
    df_journal['datetime'] = df_journal['timestamp'].apply(lambda x: pd.to_datetime(int(x), unit='ms') if str(x).isdigit() else pd.to_datetime(str(x).replace("Z", "")))
    df_journal = df_journal.dropna(subset=['datetime']).sort_values('datetime')
    df_journal['date'] = df_journal['datetime'].dt.date
    
    # Print Markdown Analysis report
    print("\n# Raw System Signal Accuracy vs. Executed Trades")
    print(f"Analysis Period: {df_res['date'].min()} to {df_res['date'].max()}")
    print(f"Total Signals Checked: {len(df_res)} distinct setups")
    print(f"Total Executed SYSTEM Trades: {len(df_journal)} trades\n")
    
    print("## 1. High-Level Performance Divergence")
    print("| Metric | ALL Signals (Vetted) | EXECUTED SYSTEM Trades |")
    print("| :--- | :---: | :---: |")
    print(f"| **Total Setups / Trades** | {len(df_res)} | {len(df_journal)} |")
    
    all_wins = len(df_res[df_res['outcome'] == 'WIN'])
    all_losses = len(df_res[df_res['outcome'] == 'LOSS'])
    all_wr = (all_wins / len(df_res)) * 100
    
    exec_wins = len(df_journal[df_journal['pnl'] > 0])
    exec_losses = len(df_journal[df_journal['pnl'] <= 0])
    exec_wr = (exec_wins / len(df_journal)) * 100
    
    print(f"| **Win Rate** | {all_wr:.2f}% ({all_wins}W / {all_losses}L) | {exec_wr:.2f}% ({exec_wins}W / {exec_losses}L) |")
    
    # Net R-Multiple
    all_net_r = df_res['r_multiple'].sum()
    exec_net_r = df_journal['pnl'].sum() / 200.0  # Assuming standard $200 risk per trade
    
    print(f"| **Net R-Multiple** | **{all_net_r:+.2f} R** | **{exec_net_r:+.2f} R** |")
    
    # Average R per trade
    print(f"| **Average R per Trade** | {df_res['r_multiple'].mean():+.2f} R | {df_journal['pnl'].mean() / 200.0:+.2f} R |")
    
    # Profit Factor
    all_pf = abs(df_res[df_res['r_multiple'] > 0]['r_multiple'].sum() / df_res[df_res['r_multiple'] < 0]['r_multiple'].sum())
    exec_pf = abs(df_journal[df_journal['pnl'] > 0]['pnl'].sum() / df_journal[df_journal['pnl'] < 0]['pnl'].sum())
    print(f"| **Profit Factor** | {all_pf:.2f} | {exec_pf:.2f} |\n")
    
    print("## 2. The Directional Edge: LONG vs. SHORT Bias")
    print("This table breaks down every vetted opportunity by asset and direction. There is a massive structural performance gap:")
    print("\n| Asset & Direction | Signals | Win Rate | Net R-Multiple |")
    print("| :--- | :---: | :---: | :---: |")
    
    for sym in ['BTC/USD', 'ETH/USD', 'SOL/USD']:
        sym_df = df_res[df_res['symbol'] == sym]
        for direction in ['LONG', 'SHORT']:
            dir_df = sym_df[sym_df['direction'] == direction]
            if not dir_df.empty:
                d_wins = len(dir_df[dir_df['outcome'] == 'WIN'])
                d_total = len(dir_df)
                d_wr = (d_wins / d_total) * 100
                d_r = dir_df['r_multiple'].sum()
                print(f"| **{sym} {direction}** | {d_total} | {d_wr:.1f}% | {d_r:+.2f} R |")
                
    # ------------------- PLOTTING -------------------
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # Plot 1: Cumulative Performance of Vetted Signals (LONG vs SHORT)
    df_res = df_res.sort_values('date')
    df_res['cum_r'] = df_res['r_multiple'].cumsum()
    
    long_cum = df_res[df_res['direction'] == 'LONG'].copy()
    long_cum['cum_r'] = long_cum['r_multiple'].cumsum()
    short_cum = df_res[df_res['direction'] == 'SHORT'].copy()
    short_cum['cum_r'] = short_cum['r_multiple'].cumsum()
    
    axes[0, 0].plot(df_res['date'].unique(), df_res.groupby('date')['r_multiple'].sum().cumsum(), label='Combined Signals', color='white', linewidth=2.5, linestyle='--')
    axes[0, 0].plot(short_cum['date'], short_cum['cum_r'], label='All SHORT Signals', color=accent_color, linewidth=2)
    axes[0, 0].plot(long_cum['date'], long_cum['cum_r'], label='All LONG Signals', color=secondary_color, linewidth=2)
    axes[0, 0].set_title('CUMULATIVE PERFORMANCE BY DIRECTION (ALL SIGNALS)', fontsize=12, fontweight='bold', pad=15)
    axes[0, 0].set_ylabel('Cumulative R-Multiple', fontsize=10)
    axes[0, 0].grid(True, linestyle='--', alpha=0.15, color=muted_gray)
    axes[0, 0].legend(facecolor='black', edgecolor=muted_gray)
    axes[0, 0].axhline(0, color='white', linewidth=0.8, alpha=0.5)
    
    # Plot 2: Performance by Asset (Cumulative R-Multiple)
    for sym, color in zip(['SOL/USD', 'BTC/USD', 'ETH/USD'], [accent_color, system_color, '#bf55ec']):
        sym_cum = df_res[df_res['symbol'] == sym].copy()
        sym_cum['cum_r'] = sym_cum['r_multiple'].cumsum()
        axes[0, 1].plot(sym_cum['date'], sym_cum['cum_r'], label=sym, color=color, linewidth=2)
        
    axes[0, 1].set_title('CUMULATIVE PERFORMANCE BY ASSET (ALL SIGNALS)', fontsize=12, fontweight='bold', pad=15)
    axes[0, 1].set_ylabel('Cumulative R-Multiple', fontsize=10)
    axes[0, 1].grid(True, linestyle='--', alpha=0.15, color=muted_gray)
    axes[0, 1].legend(facecolor='black', edgecolor=muted_gray)
    axes[0, 1].axhline(0, color='white', linewidth=0.8, alpha=0.5)
    
    # Plot 3: Win Rate by Pattern (Bar chart)
    pattern_stats = df_res.groupby('pattern').agg(
        wins=('outcome', lambda x: (x == 'WIN').sum()),
        total=('outcome', 'count')
    ).reset_index()
    pattern_stats['win_rate'] = (pattern_stats['wins'] / pattern_stats['total']) * 100
    pattern_stats = pattern_stats.sort_values('win_rate', ascending=False).head(8) # Top 8 patterns
    
    bars = axes[1, 0].barh(pattern_stats['pattern'], pattern_stats['win_rate'], color=system_color, alpha=0.8, edgecolor='white')
    # Highlight bearish patterns
    for bar, pat in zip(bars, pattern_stats['pattern']):
        if 'Bearish' in pat:
            bar.set_color(accent_color)
            bar.set_alpha(0.8)
        elif 'Bullish' in pat:
            bar.set_color(secondary_color)
            bar.set_alpha(0.8)
            
    axes[1, 0].set_title('WIN RATE BY PATTERN (TOP 8 PATTERNS)', fontsize=12, fontweight='bold', pad=15)
    axes[1, 0].set_xlabel('Win Rate (%)', fontsize=10)
    axes[1, 0].grid(True, axis='x', linestyle='--', alpha=0.15, color=muted_gray)
    axes[1, 0].axvline(50, color='yellow', linestyle=':', label='50% Threshold', alpha=0.7)
    axes[1, 0].legend(facecolor='black', edgecolor=muted_gray)
    
    # Plot 4: System Trade Selection (All Signals vs Executed PnL Distribution)
    # Aggregate daily returns
    daily_signals = df_res.groupby('date')['r_multiple'].sum()
    daily_executed = df_journal.groupby('date')['pnl'].sum() / 200.0
    
    sns.histplot(daily_signals, kde=True, ax=axes[1, 1], color=system_color, label='ALL Signals (If all taken)', alpha=0.4, bins=15)
    sns.histplot(daily_executed, kde=True, ax=axes[1, 1], color=accent_color, label='EXECUTED Trades (Actual)', alpha=0.4, bins=15)
    
    axes[1, 1].set_title('DAILY P&L DISTRIBUTION: ALL SIGNALS vs ACTUALLY TAKEN', fontsize=12, fontweight='bold', pad=15)
    axes[1, 1].set_xlabel('Daily Return (in R-Units)', fontsize=10)
    axes[1, 1].set_ylabel('Frequency', fontsize=10)
    axes[1, 1].grid(True, linestyle='--', alpha=0.15, color=muted_gray)
    axes[1, 1].axvline(0, color='white', linewidth=1)
    axes[1, 1].legend(facecolor='black', edgecolor=muted_gray)
    
    plt.suptitle('THE BAYESIAN PIVOT: SYSTEM SIGNAL ACCURACY & SELECTION BIAS', fontsize=16, fontweight='bold', y=0.96)
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    
    os.makedirs('docs/images', exist_ok=True)
    plot_path = 'docs/images/all_signals_accuracy_analysis.png'
    plt.savefig(plot_path, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"\n📊 Accuracy dashboard saved successfully to: {plot_path}")

if __name__ == '__main__':
    run_analysis()

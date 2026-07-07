import sqlite3
import pandas as pd
from datetime import datetime

def parse_time(time_str):
    if not time_str:
        return None
    try:
        if str(time_str).isdigit() or (isinstance(time_str, float) and time_str > 1e11):
            return datetime.utcfromtimestamp(float(time_str) / 1000.0)
        return datetime.fromisoformat(str(time_str).replace('Z', '+00:00')).replace(tzinfo=None)
    except Exception:
        return None

def analyze_missed_distinct():
    conn = sqlite3.connect('data/smc_alpha.db')
    
    # Load all scans
    df_scans = pd.read_sql_query("SELECT * FROM scans", conn)
    # Load all journal entries
    df_journal = pd.read_sql_query("SELECT * FROM journal", conn)
    
    conn.close()
    
    # Parse timestamps
    df_scans['parsed_time'] = df_scans['timestamp'].apply(parse_time)
    df_journal['parsed_time'] = df_journal['timestamp'].apply(parse_time)
    
    df_scans = df_scans.dropna(subset=['parsed_time'])
    df_journal = df_journal.dropna(subset=['parsed_time'])
    
    # Filter scans to get raw "Valid Trade Signals"
    valid_signals = df_scans[
        (df_scans['verdict'] == 'ACCEPTED') | 
        ((df_scans['verdict'] == 'HARD_LOGIC_PASS') & (df_scans['ai_score'] >= 8.0))
    ].copy()
    
    # Sort by timestamp ascending to process chronologically
    valid_signals = valid_signals.sort_values(by='parsed_time')
    
    # Group consecutive signals (within 4 hours of the same symbol and pattern/direction)
    distinct_signals = []
    
    for _, scan in valid_signals.iterrows():
        is_duplicate = False
        scan_time = scan['parsed_time']
        scan_dir = str(scan.get('direction') or '').upper()
        
        for logged in distinct_signals:
            if logged['symbol'] == scan['symbol'] and str(logged.get('direction') or '').upper() == scan_dir:
                time_diff = (scan_time - logged['parsed_time']).total_seconds()
                if 0 <= time_diff < 14400: # 4 hours
                    is_duplicate = True
                    break
        
        if not is_duplicate:
            distinct_signals.append(scan.to_dict())
            
    df_distinct = pd.DataFrame(distinct_signals)
    
    print(f"Total Raw Scans: {len(df_scans)}")
    print(f"Total Vetted Scans (Score >= 8): {len(valid_signals)}")
    print(f"Distinct Trade Opportunities (4H Grouped): {len(df_distinct)}")
    print(f"Total Executed Journal Trades: {len(df_journal)}")
    
    missed_count = 0
    taken_count = 0
    missed_list = []
    taken_list = []
    
    for _, scan in df_distinct.iterrows():
        scan_time = scan['parsed_time']
        scan_dir = str(scan.get('direction') or '')
        scan_bias = str(scan.get('bias') or '')
        scan_direction = (scan_dir + " " + scan_bias).upper()
        
        match = None
        for _, trade in df_journal.iterrows():
            if trade['symbol'] == scan['symbol']:
                trade_side = str(trade['side']).upper()
                
                # Correct direction mapping:
                # LONG, BULLISH, BUY -> BUY
                # SHORT, BEARISH, SELL -> SELL
                dir_match = (
                    (('BULLISH' in scan_direction or 'LONG' in scan_direction or 'BUY' in scan_direction) and trade_side == 'BUY') or
                    (('BEARISH' in scan_direction or 'SHORT' in scan_direction or 'SELL' in scan_direction) and trade_side == 'SELL')
                )
                
                if dir_match:
                    time_diff = abs((trade['parsed_time'] - scan_time).total_seconds())
                    if time_diff < 1800: # 30 mins
                        match = trade
                        break
        
        if match is not None:
            taken_count += 1
            taken_list.append({
                'timestamp': scan['timestamp'],
                'symbol': scan['symbol'],
                'pattern': scan['pattern'],
                'bias': scan['bias'],
                'ai_score': scan['ai_score'],
                'pnl': match['pnl']
            })
        else:
            missed_count += 1
            missed_list.append({
                'timestamp': scan['timestamp'],
                'symbol': scan['symbol'],
                'pattern': scan['pattern'],
                'bias': scan['bias'],
                'ai_score': scan['ai_score'],
                'verdict': scan['verdict']
            })
            
    print(f"\nDistinct System Trades Taken: {taken_count} ({taken_count/len(df_distinct)*100:.1f}%)")
    print(f"Distinct System Trades Missed: {missed_count} ({missed_count/len(df_distinct)*100:.1f}%)")
    
    df_taken = pd.DataFrame(taken_list)
    df_missed = pd.DataFrame(missed_list)
    
    if not df_taken.empty:
        print(f"\n=== PnL of Taken System Signals ===")
        print(f"Total PnL: ${df_taken['pnl'].sum():,.2f}")
        print(f"Average PnL: ${df_taken['pnl'].mean():,.2f}")
        
    if not df_missed.empty:
        print("\n=== SAMPLE OF MISSED SYSTEM SIGNALS (Last 10) ===")
        df_missed = df_missed.sort_values(by='timestamp', ascending=False)
        print(df_missed.head(10).to_string(index=False))

if __name__ == '__main__':
    analyze_missed_distinct()

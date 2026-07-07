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

def find_matches():
    conn = sqlite3.connect('data/smc_alpha.db')
    
    df_journal = pd.read_sql_query("SELECT * FROM journal WHERE strategy='SYSTEM'", conn)
    df_scans = pd.read_sql_query("SELECT * FROM scans", conn)
    conn.close()
    
    df_journal['parsed_time'] = df_journal['timestamp'].apply(parse_time)
    df_scans['parsed_time'] = df_scans['timestamp'].apply(parse_time)
    
    matches = []
    
    for _, trade in df_journal.iterrows():
        trade_time = trade['parsed_time']
        if not trade_time: continue
        
        # Search all scans for a match within 30 mins
        best_match = None
        min_diff = 1800
        
        for _, scan in df_scans.iterrows():
            if scan['symbol'] == trade['symbol']:
                scan_dir = str(scan.get('direction') or '')
                scan_bias = str(scan.get('bias') or '')
                scan_direction = (scan_dir + " " + scan_bias).upper()
                trade_side = str(trade['side']).upper()
                
                dir_match = (
                    (('BULLISH' in scan_direction or 'LONG' in scan_direction or 'BUY' in scan_direction) and trade_side == 'BUY') or
                    (('BEARISH' in scan_direction or 'SHORT' in scan_direction or 'SELL' in scan_direction) and trade_side == 'SELL')
                )
                
                if dir_match:
                    time_diff = abs((trade_time - scan['parsed_time']).total_seconds())
                    if time_diff < min_diff:
                        min_diff = time_diff
                        best_match = scan
                        
        if best_match is not None:
            matches.append({
                'trade_timestamp': trade['timestamp'],
                'trade_pnl': trade['pnl'],
                'symbol': trade['symbol'],
                'side': trade['side'],
                'scan_timestamp': best_match['timestamp'],
                'verdict': best_match['verdict'],
                'ai_score': best_match['ai_score'],
                'pattern': best_match['pattern']
            })
            
    df_matches = pd.DataFrame(matches)
    print(f"Total SYSTEM trades in journal: {len(df_journal)}")
    print(f"Matched trades to any scan in database: {len(df_matches)}")
    
    if not df_matches.empty:
        print("\n=== Matched Scan Verdicts ===")
        print(df_matches['verdict'].value_counts())
        
        print("\n=== Matched Scan AI Scores ===")
        print(df_matches['ai_score'].value_counts())
        
        print("\n=== Sample of Matched Trades and Scans ===")
        print(df_matches[['trade_timestamp', 'trade_pnl', 'verdict', 'ai_score', 'pattern']].head(10).to_string())

if __name__ == '__main__':
    find_matches()

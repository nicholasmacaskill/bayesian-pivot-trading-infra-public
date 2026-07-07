import sqlite3
import pandas as pd
import numpy as np

def verify_data():
    conn = sqlite3.connect('data/smc_alpha.db')
    df = pd.read_sql_query("SELECT * FROM journal", conn)
    conn.close()
    
    print(f"Total records in journal table: {len(df)}")
    
    system_df = df[df['strategy'] == 'SYSTEM']
    rogue_df = df[df['strategy'] == 'ROGUE']
    
    print("\n=== SYSTEM Trades PnL Distribution ===")
    print(system_df['pnl'].describe())
    
    print("\n=== ROGUE Trades PnL Distribution ===")
    print(rogue_df['pnl'].describe())
    
    # Check for extreme outliers (trades with PnL > 3 standard deviations from mean)
    sys_mean = system_df['pnl'].mean()
    sys_std = system_df['pnl'].std()
    outliers = system_df[np.abs(system_df['pnl'] - sys_mean) > (3 * sys_std)]
    
    print(f"\nSYSTEM Outliers (>3 std dev): {len(outliers)}")
    if not outliers.empty:
        print(outliers[['timestamp', 'symbol', 'side', 'pnl']])
        
    # Check for duplicate trades (same timestamp, symbol, and side)
    duplicates = df[df.duplicated(subset=['timestamp', 'symbol', 'side', 'pnl'], keep=False)]
    print(f"\nPotential duplicate entries: {len(duplicates)}")
    if len(duplicates) > 0:
        print(duplicates[['timestamp', 'symbol', 'side', 'pnl']].head(10))

if __name__ == '__main__':
    verify_data()

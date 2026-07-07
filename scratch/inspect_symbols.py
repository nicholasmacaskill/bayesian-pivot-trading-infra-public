import sqlite3
import pandas as pd

def inspect_symbols():
    conn = sqlite3.connect('data/smc_alpha.db')
    
    df_journal = pd.read_sql_query("SELECT DISTINCT symbol, strategy FROM journal", conn)
    df_scans = pd.read_sql_query("SELECT DISTINCT symbol FROM scans", conn)
    
    print("=== Journal Symbols ===")
    print(df_journal)
    
    print("\n=== Scans Symbols ===")
    print(df_scans)
    
    # Let's inspect a few records of system trades
    df_sys_journal = pd.read_sql_query("SELECT timestamp, symbol, side, pnl, strategy FROM journal WHERE strategy='SYSTEM' LIMIT 5", conn)
    print("\n=== Sample SYSTEM journal trades ===")
    print(df_sys_journal)
    
    conn.close()

if __name__ == '__main__':
    inspect_symbols()

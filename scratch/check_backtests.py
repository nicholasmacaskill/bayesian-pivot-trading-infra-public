import sqlite3
import pandas as pd

def check_backtests():
    conn = sqlite3.connect('data/smc_alpha.db')
    
    # Check if backtest_results table has data
    try:
        df = pd.read_sql_query("SELECT * FROM backtest_results", conn)
        print(f"Total backtest results saved: {len(df)}")
        if not df.empty:
            print("\n=== Backtest Summary ===")
            print(df.head(10).to_string())
    except Exception as e:
        print(f"Error checking backtests: {e}")
        
    conn.close()

if __name__ == '__main__':
    check_backtests()

import sys
import os
from dotenv import load_dotenv

sys.path.append(os.getcwd())
from src.engines.smc_scanner import SMCScanner

def check_1h():
    load_dotenv('.env.local')
    scanner = SMCScanner()
    df = scanner.fetch_data('BTC/USD', '1h', limit=100)
    if df is not None:
        fvgs = scanner.detect_fvgs(df)
        print("1-HOUR FVGs (Last 100 candles):")
        for f in fvgs:
            print(f"- {f['type']} at {f['level']} (Zone: {f.get('bottom')} - {f.get('top')})")

if __name__ == '__main__':
    check_1h()

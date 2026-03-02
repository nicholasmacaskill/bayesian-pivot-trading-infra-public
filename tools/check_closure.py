from src.engines.smc_scanner import SMCScanner
import pandas as pd
from datetime import datetime, timedelta

def check_candle_closure():
    scanner = SMCScanner()
    symbol = "BTC/USD"
    target_level = 65812.57
    
    print(f"Checking closure status for level: ${target_level:,.2f}")
    
    timeframes = ['15m', '1h', '4h']
    
    for tf in timeframes:
        df = scanner.exchange.fetch_ohlcv(symbol, timeframe=tf, limit=2)
        last_closed = df[0]
        current = df[1]
        
        # current[4] is the active price
        print(f"\n--- {tf} Timeframe ---")
        print(f"Active Price: ${current[4]:,.2f}")
        
        if current[4] < target_level:
            print(f"⚠️ Currently TRADING BELOW level.")
        else:
            print(f"✅ Currently TRADING ABOVE level.")
            
        # Last closed candle info
        if last_closed[4] < target_level:
             print(f"🚨 Last candle CLOSED BELOW level: ${last_closed[4]:,.2f}")
        else:
             print(f"🛡️ Last candle CLOSED ABOVE level: ${last_closed[4]:,.2f}")

if __name__ == "__main__":
    check_candle_closure()

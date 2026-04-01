import sys
import os
import pandas as pd
from datetime import datetime

sys.path.append(os.getcwd())
from src.engines.smc_scanner import SMCScanner
from src.core.config import Config

def scan_bullish_obs():
    scanner = SMCScanner()
    symbol = 'BTC/USD'
    
    print(f'🧱 Scanning for Bullish OBs below current price...')
    
    # 1. Fetch current price
    df_now = scanner.fetch_data(symbol, '1m', limit=1, synchronized=False)
    if df_now is None: 
        print("Could not fetch current price.")
        return
    current_price = df_now.iloc[-1]['close']
    print(f"💰 Current Price: ${current_price:,.2f}")

    for tf in ['1h', '4h']:
        print(f'\n🔍 Checking {tf}...')
        
        if tf == '1h':
            ohlcv = scanner.exchange.fetch_ohlcv(symbol, '1h', limit=100)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        else:
            # Aggregate 4h from 1h
            ohlcv_1h = scanner.exchange.fetch_ohlcv(symbol, '1h', limit=400)
            df_1h = pd.DataFrame(ohlcv_1h, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df_1h['timestamp'] = pd.to_datetime(df_1h['timestamp'], unit='ms')
            df = scanner._aggregate_ohlcv(df_1h, '4h')
        
        if 'timestamp' not in df.columns:
             df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        # Simple OB detection: Last down candle before an impulsive up move
        for i in range(1, len(df)-1):
            c1 = df.iloc[i-1]
            c2 = df.iloc[i]   # Potential OB
            c3 = df.iloc[i+1] # Impulse
            
            body_c2 = c2['close'] - c2['open']
            body_c3 = c3['close'] - c3['open']
            
            if body_c3 > 0 and c3['close'] > c2['high'] and body_c3 > abs(body_c2) * 1.5:
                ob_top = c2['high']
                ob_bottom = c2['low']
                ob_time = c2['timestamp']
                
                if ob_top < current_price:
                    # Check mitigation
                    mitigation_low = df.iloc[i+2:]['low'].min() if i+2 < len(df) else 999999
                    
                    if mitigation_low > ob_top:
                        print(f'  ✅ UNMITIGATED BULLISH OB ({tf}): ${ob_bottom:,.2f} - ${ob_top:,.2f} (Created: {ob_time})')
                    else:
                        print(f'  🛡️  MITIGATED OB ({tf}): ${ob_bottom:,.2f} - ${ob_top:,.2f} (Created: {ob_time})')

if __name__ == '__main__':
    scan_bullish_obs()

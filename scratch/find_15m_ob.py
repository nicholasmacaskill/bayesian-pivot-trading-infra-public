import os
import sys
import pandas as pd
from dotenv import load_dotenv

# Add the project root to sys.path
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner

def find_15m_ob():
    load_dotenv('.env.local')
    scanner = SMCScanner()
    symbol = "BTC/USD"
    df = scanner.fetch_data(symbol, '15m', limit=200)
    if df is None: return
    
    # Repurpose the OB logic from detect_htf_pois
    pois = []
    for i in range(10, len(df)-1):
        body_prev = abs(df['close'].iloc[i] - df['open'].iloc[i])
        body_curr = abs(df['close'].iloc[i+1] - df['open'].iloc[i+1])
        
        # Bullish Engulfing (Potential Bullish OB)
        if df['close'].iloc[i+1] > df['high'].iloc[i] and body_curr > body_prev * 2:
            pois.append({
                'type': 'OB_BULLISH',
                'top': df['high'].iloc[i],
                'bottom': df['low'].iloc[i],
                'level': (df['high'].iloc[i] + df['low'].iloc[i]) / 2,
                'index': i
            })
    
    current_price = df.iloc[-1]['close']
    print(f"Current Price: {current_price}")
    
    # Get the latest unmitigated one
    for p in reversed(pois):
        # Check if any candle after i+1 has touched the OB
        mitigated = False
        for j in range(p['index'] + 2, len(df)):
            if df['low'].iloc[j] <= p['top'] and df['high'].iloc[j] >= p['bottom']:
                mitigated = True
                break
        
        status = "MITIGATED" if mitigated else "UNMITIGATED"
        print(f"[{status}] 15m OB: {p['bottom']:.2f} - {p['top']:.2f}")
        if not mitigated:
            # Check if current price is near or just tapped it
            if df['low'].iloc[-1] <= p['top']:
                print(f"🎯 CURRENTLY TAPPING THIS OB!")

if __name__ == "__main__":
    find_15m_ob()

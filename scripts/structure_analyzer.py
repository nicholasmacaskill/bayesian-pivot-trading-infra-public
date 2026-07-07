import sqlite3
import pandas as pd
import numpy as np
import ccxt
import time
from datetime import datetime

def find_swings(df, window=5):
    # Very basic swing detection
    highs = df['high'].values
    lows = df['low'].values
    swing_highs = []
    swing_lows = []
    
    for i in range(window, len(df) - window):
        is_sh = True
        is_sl = True
        for j in range(1, window + 1):
            if highs[i] <= highs[i-j] or highs[i] <= highs[i+j]: is_sh = False
            if lows[i] >= lows[i-j] or lows[i] >= lows[i+j]: is_sl = False
        if is_sh: swing_highs.append((i, highs[i]))
        if is_sl: swing_lows.append((i, lows[i]))
        
    return swing_highs, swing_lows

def check_choch(df, swing_highs, swing_lows, side):
    # If BUY, we want to see a Bullish CHoCH (price breaking the last Swing High)
    # If SELL, we want to see a Bearish CHoCH (price breaking the last Swing Low)
    if not swing_highs or not swing_lows: return False
    
    current_close = df.iloc[-1]['close']
    last_sh_idx, last_sh_val = swing_highs[-1]
    last_sl_idx, last_sl_val = swing_lows[-1]
    
    if side == 'BUY':
        # Did price break the last swing high recently?
        if current_close > last_sh_val and (len(df) - last_sh_idx) < 15:
            return True
    else:
        if current_close < last_sl_val and (len(df) - last_sl_idx) < 15:
            return True
    return False

def find_fvg(df, side):
    fvgs = []
    # Loop over last 30 candles looking for FVGs
    for i in range(len(df)-30, len(df)-1):
        c1 = df.iloc[i-2]
        c2 = df.iloc[i-1]
        c3 = df.iloc[i]
        
        if side == 'BUY':
            # Bullish FVG: low of c3 > high of c1
            if c3['low'] > c1['high']:
                fvgs.append((c1['high'], c3['low'])) # FVG zone
        else:
            # Bearish FVG: high of c3 < low of c1
            if c3['high'] < c1['low']:
                fvgs.append((c3['high'], c1['low'])) # FVG zone
    return fvgs

def analyze_structure():
    print("🏛️ Initializing Deep Structural Analysis Engine...")
    conn = sqlite3.connect('data/smc_alpha.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM journal WHERE pnl > 0 AND strategy = 'ROGUE' ORDER BY timestamp DESC LIMIT 30")
    wins = cursor.fetchall()
    
    exchange = ccxt.binance({'enableRateLimit': True})
    
    fvg_taps = 0
    choch_entries = 0
    total_processed = 0
    
    for idx, row in enumerate(wins):
        d = dict(row)
        try:
            trade_time = datetime.fromisoformat(d['timestamp'].replace('Z', '+00:00'))
            ts_ms = int(trade_time.timestamp() * 1000)
            since = ts_ms - (200 * 5 * 60 * 1000)
            
            ohlcv = exchange.fetch_ohlcv(d['symbol'].replace("USD", "USDT"), '5m', since, 200)
            if not ohlcv: continue
            
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Structural Analysis
            swing_highs, swing_lows = find_swings(df)
            has_choch = check_choch(df, swing_highs, swing_lows, d['side'])
            fvgs = find_fvg(df, d['side'])
            
            current_price = df.iloc[-1]['close']
            
            # Check for sniper tap into FVG
            is_fvg_tap = False
            for bot, top in fvgs:
                if bot <= current_price <= top:
                    is_fvg_tap = True
                    break
                    
            if has_choch: choch_entries += 1
            if is_fvg_tap: fvg_taps += 1
            total_processed += 1
            
            print(f"[{idx+1}/{len(wins)}] {d['symbol']} {d['side']} | CHoCH Confirm: {has_choch} | FVG Sniper Tap: {is_fvg_tap}")
            time.sleep(0.5)
            
        except Exception as e:
            pass

    print("\n" + "="*50)
    print("🏛️ THE STRUCTURAL DNA MATRIX 🏛️")
    print("="*50)
    print(f"Total Trades Analyzed: {total_processed}")
    if total_processed > 0:
        print(f"1. CHoCH Confirmations: {(choch_entries/total_processed)*100:.1f}% of manual wins occurred right after a structural Change of Character.")
        print(f"2. FVG Sniper Taps: {(fvg_taps/total_processed)*100:.1f}% of manual wins were sniper entries directly into a 5-minute Fair Value Gap.")
    print("\nThis structural signature is the missing link to your automated Edge.")

if __name__ == "__main__":
    analyze_structure()

import os
import json
import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta
from src.core.supabase_client import supabase

# Ensure we're in the right directory
os.chdir('/Users/nicholasmacaskill/sovereignSMC/bayesian-pivot-trading-infra')

def forensic_audit(days=14):
    print(f"--- 🚀 RECALIBRATING FORENSIC AUDIT (Concurrency Filter) ---")
    if not supabase.client:
        print("❌ Supabase connection failed.")
        return

    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    resp = supabase.client.table("scans")\
        .select("*")\
        .gt("ai_score", 7.0)\
        .gt("timestamp", cutoff)\
        .order("timestamp", desc=False)\
        .execute()
    
    signals = resp.data if resp.data else []
    if not signals: return

    symbol_map = {"BTC/USD": "BTC-USD", "ETH/USD": "ETH-USD", "SOL/USD": "SOL-USD"}
    
    # Pre-fetch data for the crypto symbols only
    data_cache = {}
    for sym, yf_sym in symbol_map.items():
        print(f"Fetching 5m historical data for {sym}...")
        df = yf.download(yf_sym, start=(datetime.utcnow() - timedelta(days=days+2)).strftime('%Y-%m-%d'), interval="5m")
        if df.empty: continue
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        if df.index.tz is not None: df.index = df.index.tz_localize(None)
        data_cache[sym] = df

    # Track open positions per symbol
    open_until = {sym: datetime.min for sym in symbol_map.keys()}
    results = []
    total_r = 0.0
    wins, losses = 0, 0

    for s in signals:
        sym = s['symbol']
        
        # Skip unknown symbols (like MOCK/USD)
        if sym not in symbol_map: continue
        
        sig_time = pd.to_datetime(s['timestamp']).tz_localize(None)
        
        # SKIP if we are already in a trade for this symbol
        if sig_time < open_until.get(sym, datetime.min):
            continue
            
        if sym not in data_cache: continue
        df = data_cache[sym]
        after_sig = df[df.index >= sig_time]
        if after_sig.empty: continue
        
        try:
            val = after_sig.iloc[0]['Open']
            entry_price = float(val.iloc[0] if hasattr(val, 'iloc') else val)
        except: continue
        
        before_sig = df[df.index < sig_time].tail(12)
        if before_sig.empty: continue
        
        direction = 'LONG' if 'Bullish' in s['pattern'] else 'SHORT'
        try:
            if direction == 'LONG':
                low_val = before_sig['Low'].min()
                sl = float(low_val.iloc[0] if hasattr(low_val, 'iloc') else low_val)
                risk = abs(entry_price - sl)
                if risk == 0: risk = entry_price * 0.001
                tp = entry_price + (2.5 * risk)
            else:
                high_val = before_sig['High'].max()
                sl = float(high_val.iloc[0] if hasattr(high_val, 'iloc') else high_val)
                risk = abs(sl - entry_price)
                if risk == 0: risk = entry_price * 0.001
                tp = entry_price - (2.5 * risk)
        except: continue

        audit_window = after_sig.head(288) # Max 24 hour hold
        hit_tp, hit_sl = False, False
        exit_time = sig_time + timedelta(hours=24)
        
        for t, row in audit_window.iterrows():
            try:
                h = float(row['High'].iloc[0] if hasattr(row['High'], 'iloc') else row['High'])
                l = float(row['Low'].iloc[0] if hasattr(row['Low'], 'iloc') else row['Low'])
            except: continue
            
            if direction == 'LONG':
                if l <= sl: hit_sl = True; exit_time = t; break
                if h >= tp: hit_tp = True; exit_time = t; break
            else:
                if h >= sl: hit_sl = True; exit_time = t; break
                if l <= tp: hit_tp = True; exit_time = t; break
        
        if hit_tp:
            total_r += 2.5; wins += 1
        elif hit_sl:
            total_r -= 1.0; losses += 1
            
        # Set "Cooldown" until this trade was resolved
        open_until[sym] = exit_time

    total_trades = wins + losses
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    print("\n" + "="*40)
    print("📈 SOVEREIGN REALISTIC AUDIT (Last 14 Days)")
    print("="*40)
    print(f"Realistic Trades:         {total_trades}")
    print(f"Wins:                     {wins}")
    print(f"Losses:                   {losses}")
    print(f"Win Rate:                 {win_rate:.1f}%")
    print(f"Total Cumulative Alpha:   {total_r:+.1f}R")
    print("="*40)
    print(f"Hypothetical Profit @ 1% Risk ($100k): ${total_r * 1000:,.2f}")
    print("="*40)

if __name__ == "__main__":
    forensic_audit(14)

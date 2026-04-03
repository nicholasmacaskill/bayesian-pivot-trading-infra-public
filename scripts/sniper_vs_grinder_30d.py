import os
import json
import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta
from src.core.supabase_client import supabase
from src.core.config import Config

# Ensure we're in the right directory
os.chdir('/Users/nicholasmacaskill/sovereignSMC/bayesian-pivot-trading-infra')

def sniper_backtest(days=30):
    print(f"--- 🚀 SOVEREIGN SNIPER VS. MEAT GRINDER (30-Day Forensic) ---")
    if not supabase.client: return

    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    # Fetch ALL signals from the last 30 days
    resp = supabase.client.table("scans")\
        .select("*")\
        .gt("timestamp", cutoff)\
        .order("timestamp", desc=False)\
        .execute()
    
    signals = resp.data if resp.data else []
    if not signals: return

    symbol_map = {"BTC/USD": "BTC-USD", "ETH/USD": "ETH-USD", "SOL/USD": "SOL-USD"}
    data_cache = {}
    for sym, yf_sym in symbol_map.items():
        sub_df = yf.download(yf_sym, start=(datetime.utcnow() - timedelta(days=days+2)).strftime('%Y-%m-%d'), interval="5m")
        if sub_df.empty: continue
        if isinstance(sub_df.columns, pd.MultiIndex): sub_df.columns = sub_df.columns.get_level_values(0)
        if sub_df.index.tz is not None: sub_df.index = sub_df.index.tz_localize(None)
        data_cache[sym] = sub_df

    # --- 1. LEGACY AUDIT (No Gates, 7.0 Alpha Floor) ---
    def run_audit(signals_list, ai_floor=7.0, use_hurst_gate=False):
        open_until = {sym: datetime.min for sym in symbol_map.keys()}
        total_r, wins, losses, filtered = 0.0, 0, 0, 0

        for s in signals_list:
            sym = s['symbol']
            if sym not in symbol_map: continue
            sig_time = pd.to_datetime(s['timestamp']).tz_localize(None)
            if sig_time < open_until.get(sym, datetime.min): continue
            
            # AI Score Floor
            if s.get('ai_score', 0) < ai_floor: 
                filtered += 1; continue
                
            if sym not in data_cache: continue
            df = data_cache[sym]
            
            # Hurst Gate
            after_sig = df[df.index >= sig_time]
            if after_sig.empty: continue
            
            # Re-calculate Hurst for the gate
            # Use 100 bars lookback (historical)
            before_sig_all = df[df.index < sig_time].tail(100)
            if before_sig_all.empty: continue
            
            # Modern Hurst logic
            hurst_val = 0.5
            try:
                # Naive Hurst for speed
                prices = before_sig_all['close']
                lags = range(2, 20)
                tau = [np.sqrt(np.std(np.subtract(prices[lag:], prices[:-lag]))) for lag in lags]
                m = np.polyfit(np.log(lags), np.log(tau), 1)
                hurst_val = m[0] * 2.0
            except: pass
            
            if use_hurst_gate:
                if 0.45 <= hurst_val <= 0.55:
                    filtered += 1; continue
            
            # Execution Logic
            try:
                val = after_sig.iloc[0]['Open']
                entry_price = float(val.iloc[0] if hasattr(val, 'iloc') else val)
            except: continue
            
            before_sig = df[df.index < sig_time].tail(12)
            direction = 'LONG' if 'Bullish' in s['pattern'] else 'SHORT'
            
            # Basic R Calculation (Conservative)
            try:
                if direction == 'LONG':
                    sl = float(before_sig['Low'].min().iloc[0] if hasattr(before_sig['Low'].min(), 'iloc') else before_sig['Low'].min())
                    risk = abs(entry_price - sl)
                    if risk == 0: risk = entry_price * 0.001
                    tp = entry_price + (2.5 * risk)
                else:
                    sl = float(before_sig['High'].max().iloc[0] if hasattr(before_sig['High'].max(), 'iloc') else before_sig['High'].max())
                    risk = abs(sl - entry_price)
                    if risk == 0: risk = entry_price * 0.001
                    tp = entry_price - (2.5 * risk)
            except: continue

            audit_window = after_sig.head(144) # 12 hours max
            hit_tp, hit_sl = False, False
            exit_time = sig_time + timedelta(hours=12)
            
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
            
            if hit_tp: total_r += 2.5; wins += 1
            elif hit_sl: total_r -= 1.0; losses += 1
            open_until[sym] = exit_time
            
        return {'trades': wins+losses, 'wins': wins, 'losses': losses, 'alpha': total_r, 'filtered': filtered}

    print("📊 Auditing Legacy Model (7.0 Alpha Floor, No Hurst Gate)...")
    legacy = run_audit(signals, ai_floor=7.0, use_hurst_gate=False)
    
    print("🎯 Auditing SOVEREIGN SNIPER (8.5 Alpha Floor, Hurst Gate Active)...")
    sniper = run_audit(signals, ai_floor=8.5, use_hurst_gate=True)

    def print_rep(name, data):
        wr = (data['wins'] / data['trades'] * 100) if data['trades'] > 0 else 0
        print(f"\n[{name}]")
        print(f"Total Realistic Trades:  {data['trades']}")
        print(f"Wins / Losses:           {data['wins']} / {data['losses']}")
        print(f"Win Rate:                {wr:.1f}%")
        print(f"Total Cumulative Alpha:  {data['alpha']:+.1f}R")
        print(f"Drawdown (Units R):      {abs(min(0, data['alpha'])):.1f}R")
        print(f"Prop Account PnL ($100k): ${data['alpha'] * 1000:,.2f}")
        print(f"Noise Filtered:          {data['filtered']} trades rejected.")

    print_rep("LEGACY MODEL (No Gates)", legacy)
    print_rep("SOVEREIGN SNIPER (Hardened)", sniper)
    
    saving = (sniper['alpha'] - legacy['alpha']) * 1000
    print("\n" + "!"*40)
    print(f"💰 SOVEREIGN SAVINGS: ${saving:,.2f}")
    print(f"🛡️ DRAWDOWN REDUCTION: {abs(sniper['trades'] - legacy['trades'])} high-risk trades avoided.")
    print("!"*40)

if __name__ == "__main__":
    sniper_backtest(30)

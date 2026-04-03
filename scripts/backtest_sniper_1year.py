import os
import pandas as pd
import yfinance as yf
import numpy as np
from datetime import datetime, timedelta

# Ensure we're in the right directory
os.chdir('/Users/nicholasmacaskill/sovereignSMC/bayesian-pivot-trading-infra')

def calculate_hurst(prices):
    """Naive Hurst Exponent calculation."""
    try:
        lags = range(2, 20)
        tau = [np.sqrt(np.std(np.subtract(prices[lag:], prices[:-lag]))) for lag in lags]
        m = np.polyfit(np.log(lags), np.log(tau), 1)
        return m[0] * 2.0
    except:
        return 0.5

def sniper_yearly_sim():
    print("--- 🔬 1-YEAR SOVEREIGN SNIPER SIMULATION ---")
    symbols = {"BTC/USD": "BTC-USD", "ETH/USD": "ETH-USD", "SOL/USD": "SOL-USD"}
    
    # 1. FETCH 1-YEAR HISTORICAL DATA (1h candles)
    data = {}
    for sym, yf_sym in symbols.items():
        print(f"📥 Fetching 1h data for {sym}...")
        df = yf.download(yf_sym, period="1y", interval="1h")
        if df.empty: continue
        
        # Robust Column Standardisation
        if isinstance(df.columns, pd.MultiIndex): 
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() for c in df.columns]
        
        if df.index.tz is not None: 
            df.index = df.index.tz_localize(None)
        
        data[sym] = df

    # 2. SIMULATION
    results = []
    
    for sym, df in data.items():
        print(f"⚙️ Simulating Sniper Mode for {sym}...")
        open_until = datetime.min
        
        # We need a decent lookback for Hurst (100 bars)
        for i in range(100, len(df)-24):
            sig_time = df.index[i]
            if sig_time < open_until: continue
            
            # Hurst Calculation (100 bar lookback)
            if 'close' not in df.columns: continue
            window = df.iloc[i-100:i]['close']
            hurst = calculate_hurst(window.values)
            
            # 🚫 THE SNIPER GATE: Block 0.45 - 0.55
            if 0.45 <= hurst <= 0.55: continue
            
            close = float(df.iloc[i]['close'])
            lows = df.iloc[i-12:i]['low']
            highs = df.iloc[i-12:i]['high']
            
            direction = None
            if hurst < 0.45:
                # Judas Sweep: Wick below recent low (12h) + Close above it
                recent_low = float(lows.min())
                if float(df.iloc[i]['low']) < recent_low and close > recent_low:
                    direction = 'LONG'
                # Judas Sweep: Wick above recent high (12h) + Close below it
                recent_high = float(highs.max())
                if float(df.iloc[i]['high']) > recent_high and close < recent_high:
                    direction = 'SHORT'
            
            elif hurst > 0.55:
                # Trend Alignment: Above EMA20 (simple trend proxy)
                ema20 = df.iloc[i-20:i]['close'].mean()
                if close > ema20 and float(df.iloc[i]['low']) < ema20:
                    direction = 'LONG' # RSI/EMA Pullback
                elif close < ema20 and float(df.iloc[i]['high']) > ema20:
                    direction = 'SHORT'
            
            if not direction: continue
            
            # ENTRY/SL/TP
            entry = close
            try:
                if direction == 'LONG':
                    sl_val = df.iloc[i-6:i]['low'].min()
                    sl = float(sl_val.iloc[0] if hasattr(sl_val, 'iloc') else sl_val)
                    risk = abs(entry - sl)
                    if risk == 0: risk = entry * 0.002
                    tp = entry + (3.5 * risk) # Targeted 3.5R
                else:
                    sl_val = df.iloc[i-6:i]['high'].max()
                    sl = float(sl_val.iloc[0] if hasattr(sl_val, 'iloc') else sl_val)
                    risk = abs(sl - entry)
                    if risk == 0: risk = entry * 0.002
                    tp = entry - (3.5 * risk)
            except: continue
                
            # AUDIT: Look forward
            hit_tp, hit_sl = False, False
            for j in range(i+1, min(i+48, len(df))):
                h = float(df.iloc[j]['high'].iloc[0] if hasattr(df.iloc[j]['high'], 'iloc') else df.iloc[j]['high'])
                l = float(df.iloc[j]['low'].iloc[0] if hasattr(df.iloc[j]['low'], 'iloc') else df.iloc[j]['low'])
                
                if direction == 'LONG':
                    if l <= sl: hit_sl = True; open_until = df.index[j]; break
                    if h >= tp: hit_tp = True; open_until = df.index[j]; break
                else:
                    if h >= sl: hit_sl = True; open_until = df.index[j]; break
                    if l <= tp: hit_tp = True; open_until = df.index[j]; break
            
            if hit_tp or hit_sl:
                results.append({
                    'ts': sig_time,
                    'symbol': sym,
                    'res': 'WIN' if hit_tp else 'LOSS',
                    'pnl': 3.5 if hit_tp else -1.0,
                    'month': sig_time.month,
                    'year': sig_time.year
                })

    if not results:
        print("❌ No signals met the Sovereign Sniper criteria in the last year.")
        return

    df_res = pd.DataFrame(results)
    df_res['month_year'] = df_res['year'].astype(str) + "-" + df_res['month'].astype(str).str.zfill(2)
    
    monthly = df_res.groupby('month_year')['pnl'].sum()
    monthly_wr = df_res.groupby('month_year')['res'].apply(lambda x: (x == 'WIN').sum() / len(x) * 100)

    print("\n" + "="*50)
    print("📈 SOVEREIGN SNIPER: 1-YEAR BASELINE REPORT")
    print("="*50)
    print(f"Total High-Alpha Signals: {len(df_res)}")
    print(f"Wins / Losses:           {len(df_res[df_res['res']=='WIN'])} / {len(df_res[df_res['res']=='LOSS'])}")
    print(f"Win Rate:                {(len(df_res[df_res['res']=='WIN'])/len(df_res)*100):.1f}%")
    print(f"Total Cumulative Alpha:  {df_res['pnl'].sum():+.1f} R")
    print("="*50)
    
    print("\n📅 MONTHLY PERFORMANCE (Units R):")
    for m, p in monthly.items():
        print(f"• {m}: {p:>+6.1f} R  (WR: {monthly_wr[m]:.1f}%)")
    
    print("\n" + "="*50)
    print(f"💰 PROJECTED 1-YEAR PNL ($100k Account @ 0.7% Risk):")
    # Base risk per trade from Config would be 0.7%, i.e. 0.007 * 100k = 700 USD
    print(f"Total Gain: ${df_res['pnl'].sum() * 700:,.2f}")
    print(f"Monthly Avg: ${ (df_res['pnl'].sum() * 700) / 12:,.2f} / month")
    print("="*50)

if __name__ == "__main__":
    sniper_yearly_sim()

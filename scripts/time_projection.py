import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def estimate_time():
    print("⏳ Estimating Time-to-Target ($62,000)...")
    
    # 1. Fetch Daily Data for ATR
    df = yf.download('BTC-USD', period='60d', interval='1d')
    
    # True Range calculation
    df['H-L'] = df['High'] - df['Low']
    df['H-PC'] = (df['High'] - df['Close'].shift()).abs()
    df['L-PC'] = (df['Low'] - df['Close'].shift()).abs()
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    df['ATR'] = df['TR'].rolling(14).mean()
    
    daily_atr = df['ATR'].iloc[-1]
    current_price = float(df['Close'].iloc[-1])
    target_price = 62000
    distance = current_price - target_price
    
    print(f"   Current Price: ${current_price:,.2f}")
    print(f"   Target Price: ${target_price:,.2f}")
    print(f"   Distance: ${distance:,.2f}")
    print(f"   Daily ATR (14): ${daily_atr:,.2f}")
    
    # 2. Fetch 1H Data for recent displacement speed
    df_h = yf.download('BTC-USD', period='5d', interval='1h')
    # Measure the last major downward move displacement
    # Let's find the max 4-hour drop in the last 5 days
    df_h['4h_change'] = df_h['Close'].diff(4)
    max_drop = df_h['4h_change'].min()
    print(f"   Max 4H Momentum (Recent Drop): ${abs(max_drop):,.2f}")
    
    # 3. Probability Windows
    # Average Speed Version (Standard)
    days_standard = distance / daily_atr
    
    # Accelerated Version (High Volatility/News)
    # Bearish moves often occur in 'Impulse Waves' that are 1.5x - 2.0x ATR
    days_accelerated = distance / (daily_atr * 1.5)
    
    # Slow Version (Consolidation/Grind)
    days_slow = distance / (daily_atr * 0.5)
    
    print("\n📈 Projected Arrival Windows:")
    print(f"   - ACCELERATED (High Momentum): {days_accelerated:.1f} days")
    print(f"   - STANDARD (Trend Velocity): {days_standard:.1f} days")
    print(f"   - SLOW (Range Grind): {days_slow:.1f} days")

if __name__ == "__main__":
    estimate_time()

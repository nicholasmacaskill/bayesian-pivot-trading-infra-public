import yfinance as yf
import pandas as pd

try:
    print("Fetching BTC data...")
    df = yf.download('BTC-USD', period='1d', interval='5m', progress=False)
    if not df.empty:
        # Lowercase for consistency
        df.columns = [c.lower() for c in df.columns]
        
        # Entry/Stop from alert
        entry_price = 68313.26
        stop_loss = 68509.87
        risk = stop_loss - entry_price
        
        # Targets
        tp1 = entry_price - (1.5 * risk)
        tp2 = entry_price - (3.0 * risk)
        
        # Draw on Liquidity (Recent Low)
        recent_low = df['low'].min()
        
        print(f"ENTRY: {entry_price}")
        print(f"STOP: {stop_loss}")
        print(f"TP1 (1.5R): {tp1:.2f}")
        print(f"TP2 (3.0R): {tp2:.2f}")
        print(f"DRAW ON LIQUIDITY (Recent Low): {recent_low:.2f}")
    else:
        print("Empty DF")
except Exception as e:
    print(f"Error: {e}")

from src.engines.smc_scanner import SMCScanner
from src.core.config import Config
import pandas as pd

def calculate_sl():
    scanner = SMCScanner()
    symbol = "BTC/USD"
    
    print(f"Fetching data for {symbol}...")
    df = scanner.fetch_data(symbol, "5m", limit=100)
    
    if df is None or df.empty:
        print("Failed to fetch data.")
        return

    current_price = df['close'].iloc[-1]
    
    # Calculate ATR
    atr_series = scanner.calculate_atr(df)
    current_atr = atr_series.iloc[-1]
    
    multiplier = Config.STOP_LOSS_ATR_MULTIPLIER
    stop_buffer = current_atr * multiplier
    
    # Bearish Scenario (Short)
    short_sl = current_price + stop_buffer
    
    # Bullish Scenario (Long)
    long_sl = current_price - stop_buffer
    
    print(f"\n📊 DATA SNAPSHOT")
    print(f"Current Price: ${current_price:,.2f}")
    print(f"Current ATR (14): {current_atr:.2f}")
    print(f"SL Multiplier: {multiplier}x")
    print("-" * 30)
    print(f"🔴 BEARISH STOP LOSS (Short): ${short_sl:,.2f}")
    print(f"   (Buffer: +${stop_buffer:.2f})")
    print("-" * 30)
    print(f"🟢 BULLISH STOP LOSS (Long): ${long_sl:,.2f}")
    print(f"   (Buffer: -${stop_buffer:.2f})")

if __name__ == "__main__":
    calculate_sl()

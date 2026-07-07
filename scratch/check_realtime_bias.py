import os
import sys

# Add root directory to path
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner

def main():
    print("🔍 Fetching real-time market bias...")
    scanner = SMCScanner()
    symbol = "BTC/USD"
    
    # 1. 4H Bias
    bias_4h = scanner.get_4h_bias(symbol)
    
    # 2. Daily Bias
    df_daily = scanner.fetch_data(symbol, "1d", limit=10)
    daily_bias = "Neutral"
    if df_daily is not None and not df_daily.empty:
        last_close = df_daily['close'].iloc[-1]
        prev_close = df_daily['close'].iloc[-2]
        daily_bias = "BULLISH" if last_close > prev_close else "BEARISH"
        
    print(f"\n📊 REAL-TIME CONFLUENCE FOR {symbol}:")
    print(f"• Daily Bias: {daily_bias}")
    print(f"• HTF (4H) Bias: {bias_4h}")
    
    try:
        import yfinance as yf
        dxy = yf.Ticker("DX-Y.NYB")
        dxy_hist = dxy.history(period="5d")
        if not dxy_hist.empty:
            dxy_change = dxy_hist['Close'].iloc[-1] - dxy_hist['Close'].iloc[-2]
            dxy_trend = "BEARISH" if dxy_change < 0 else "BULLISH"
            print(f"• Intermarket (DXY): {dxy_trend}")
    except Exception as e:
        print(f"• Intermarket (DXY): Fetch failed ({e})")

if __name__ == "__main__":
    main()

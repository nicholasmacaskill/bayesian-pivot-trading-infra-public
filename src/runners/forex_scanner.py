import sys
import os
import logging
from datetime import datetime, timezone

# Add the project root to the python path
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner
from src.engines.forex_engine import ForexEngine
from src.engines.seasonality_engine import SeasonalityEngine
from src.engines.news_filter import NewsFilter

logger = logging.getLogger(__name__)

class ForexAlphaScanner:
    """
    Forex-specialized scanner that combines SMC logic with 
    Sentiment, News, and Seasonality data.
    """
    
    FOREX_MAJORS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"]

    def __init__(self):
        self.smc = SMCScanner()
        self.forex_data = ForexEngine()
        self.seasonality = SeasonalityEngine()
        self.news = NewsFilter()
        
    def analyze_pair(self, symbol):
        """
        Performs a full alpha analysis on a single currency pair.
        """
        print(f"\n🌍 Analyzing {symbol} Alpha Profiles...")
        
        # 1. Fetch Data
        df_list = self.forex_data.fetch_ohlcv(symbol, timeframe='5m', limit=200)
        if not df_list:
            print(f"❌ Failed to fetch data for {symbol}")
            return None
            
        import pandas as pd
        df = pd.DataFrame(df_list, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')

        # 2. Seasonality Bias
        # Symbol mapping for yf if needed (SeasonalityEngine handles it internally if using =X)
        yf_symbol = self.forex_data.SYMBOL_MAP.get(symbol, symbol)
        seasonal_score = self.seasonality.get_current_seasonal_bias(yf_symbol)
        seasonal_dir = "BULLISH" if seasonal_score > 0.2 else ("BEARISH" if seasonal_score < -0.2 else "NEUTRAL")
        print(f"📅 Seasonal Bias ({datetime.now().strftime('%B')}): {seasonal_dir} ({seasonal_score})")

        # 3. News Context
        # We need to know which countries are involved
        base = symbol[:3]
        quote = symbol[3:]
        self.news.fetch_calendar(currencies=[base, quote])
        is_safe, event, mins = self.news.is_news_safe(buffer_minutes=60)
        
        news_status = "✅ SAFE" if is_safe else f"⚠️ VOLATILE: {event} in {mins}m"
        print(f"🗞️ News Environment: {news_status}")

        # 4. SMC Pattern Check
        # We wrap the df in the format SMCScanner expects if it were coming from CCXT
        result = self.smc.scan_pattern(symbol, timeframe="5m", provided_df=df)
        
        if result:
            setup, _ = result
            print(f"🎯 SMC PATTERN DETECTED: {setup['pattern']}")
            print(f"   Direction: {setup['direction']}")
            
            # Confluence Check
            setup_dir = setup['direction']
            alpha_confirmed = (setup_dir == "LONG" and seasonal_score > 0) or \
                             (setup_dir == "SHORT" and seasonal_score < 0)
            
            if alpha_confirmed:
                print("💎 ALPHA CONFLUENCE: Setup aligns with Seasonal tendencies.")
                setup['quality'] = "PREMIUM"
            else:
                print("⚖️ SETUP QUALITY: Standard (No Seasonal Alignment)")
                setup['quality'] = "STANDARD"
                
            setup['seasonal_score'] = seasonal_score
            setup['news_safe'] = is_safe
            
            return setup
            
        else:
            print("🌑 No immediate institutional setups found.")
            return None

    def run_full_scan(self):
        """Scans the entire Forex Majors watchlist."""
        print(f"🚀 Starting Sovereign Forex Alpha Scan...")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        
        results = []
        for pair in self.FOREX_MAJORS:
            setup = self.analyze_pair(pair)
            if setup:
                results.append(setup)
        
        print(f"\n--- Scan Complete: {len(results)} pairs found with setups ---")
        return results

if __name__ == "__main__":
    scanner = ForexAlphaScanner()
    scanner.run_full_scan()

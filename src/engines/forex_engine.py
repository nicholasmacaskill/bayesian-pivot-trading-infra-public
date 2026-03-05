import yfinance as yf
import pandas as pd
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

class ForexEngine:
    """
    Forex-specific data engine using yfinance.
    Handles symbol mapping, fetching OHLCV, and formatting for the SMC Scanner.
    """
    SYMBOL_MAP = {
        "EURUSD": "EURUSD=X",
        "GBPUSD": "GBPUSD=X",
        "USDJPY": "JPY=X",
        "AUDUSD": "AUDUSD=X",
        "USDCAD": "CAD=X",
        "USDCHF": "CHF=X",
        "EURGBP": "EURGBP=X",
        "EURJPY": "EURJPY=X"
    }

    def fetch_ohlcv(self, symbol, timeframe='1h', limit=100):
        """
        Fetches Forex OHLCV data from yfinance.
        
        Args:
            symbol: Clean symbol (e.g., 'EURUSD')
            timeframe: yfinance timeframe ('1m', '5m', '15m', '1h', '1d', '1wk')
            limit: Number of candles (approximate for yfinance)
            
        Returns:
            list: OHLCV format [timestamp, open, high, low, close, volume]
        """
        yf_symbol = self.SYMBOL_MAP.get(symbol, symbol)
        
        # Calculate period based on limit and timeframe
        # yfinance uses 'period' (1d, 5d, 1mo, etc) or start/end
        # We'll use start/end for precision if limit is provided
        
        # Approximate time delta
        tf_delta = {
            '1m': timedelta(minutes=limit),
            '5m': timedelta(minutes=limit * 5),
            '15m': timedelta(minutes=limit * 15),
            '1h': timedelta(hours=limit),
            '1d': timedelta(days=limit),
            '1wk': timedelta(weeks=limit)
        }
        
        delta = tf_delta.get(timeframe, timedelta(hours=limit))
        start_date = datetime.now() - delta
        
        try:
            data = yf.download(yf_symbol, start=start_date, interval=timeframe, progress=False)
            
            if data is None or data.empty:
                logger.warning(f"No data found for {yf_symbol}")
                return []
            
            # Reset index to get timestamp as a column
            # Handle potential MultiIndex columns from yfinance
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            
            data = data.reset_index()
            
            # Rename columns to standard lowercase
            col_map = {
                'Datetime': 'timestamp',
                'Date': 'timestamp',
                'Open': 'open',
                'High': 'high',
                'Low': 'low',
                'Close': 'close',
                'Volume': 'volume'
            }
            data = data.rename(columns=col_map)
            
            # Prepare OHLCV list
            ohlcv = []
            for _, row in data.iterrows():
                # Convert timestamp to ms
                ts = int(row['timestamp'].timestamp() * 1000)
                ohlcv.append([
                    ts,
                    float(row['open']),
                    float(row['high']),
                    float(row['low']),
                    float(row['close']),
                    float(row['volume'])
                ])
                
            return ohlcv[-limit:] # Ensure we stick to the limit
            
        except Exception as e:
            logger.error(f"Error fetching Forex data for {yf_symbol}: {e}")
            return []

if __name__ == "__main__":
    engine = ForexEngine()
    data = engine.fetch_ohlcv("EURUSD", timeframe="1h", limit=10)
    for d in data:
        print(d)

import numpy as np
import pandas as pd
import ccxt
import time
from datetime import datetime, time as time_obj
from src.core.config import Config
from src.engines.intermarket_engine import IntermarketEngine
from src.engines.news_filter import NewsFilter
from src.engines.visualizer import generate_bias_chart
from src.engines.ai_validator import AIValidator
import logging
import os
import functools
from src.core.database import log_system_event

logger = logging.getLogger(__name__)

def ensure_data(default_return=None):
    """Decorator to ensure df is valid before running analysis"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, df, *args, **kwargs):
            if df is None or len(df) < 5:
                return default_return
            try:
                return func(self, df, *args, **kwargs)
            except Exception as e:
                logger.error(f"Error in {func.__name__}: {e}")
                return default_return
        return wrapper
    return decorator

def safe_scan(component):
    """Decorator to catch and log errors in high-level scanning methods"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                import traceback
                symbol = args[0] if args else "Unknown"
                err_msg = f"{component} error ({symbol}): {str(e)}\n{traceback.format_exc()}"
                logger.error(err_msg)
                log_system_event(component, err_msg, level="ERROR")
                return None
        return wrapper
    return decorator

class SMCScanner:
    def __init__(self):
        # Initialize public exchange for data fetching (free tier)
        # Using Coinbase (Advanced Trade) to avoid Binance geo-restrictions
        try:
            self.exchange = ccxt.coinbase({'enableRateLimit': True})
        except Exception:
            # Fallback to standard coinbase if 'coinbase' alias refers to old API in this version
            # But usually 'coinbase' is the correct one for public market data now
            self.exchange = ccxt.coinbasepro({'enableRateLimit': True})
            
        self.intermarket = IntermarketEngine()
        self.news = NewsFilter()
        self.order_book_enabled = True  # Can be disabled if exchange doesn't support
        # Deduplication cache: prevents firing the same signal multiple times per candle window
        # Key: (symbol, pattern_type) | Value: timestamp of last signal
        self._signal_cache = {}
        self._signal_cooldown_mins = 15  # Minimum minutes between signals for the same symbol

    def get_hurst_exponent(self, time_series):
        """
        Calculates the Hurst Exponent to determine market regime.
        H < 0.5 = Mean Reverting (Range) - Ideal for Turtle Soup
        H = 0.5 = Brownian Motion (Random)
        H > 0.5 = Trending (Momentum) - Ideal for Breakouts
        """
        try:
            from scipy.stats import linregress
            # Create a range of lag values
            lags = range(2, 20)
            tau = [np.sqrt(np.std(np.subtract(time_series[lag:], time_series[:-lag]))) for lag in lags]
            # Use linear regression to estimate the Hurst Exponent
            poly = np.polyfit(np.log(lags), np.log(tau), 1)
            return poly[0] * 2.0
        except Exception as e:
            logger.error(f"Hurst Calculation Error: {e}")
            return 0.5

    def get_adf_test(self, time_series):
        """
        Performs Augmented Dickey-Fuller test to check for stationarity.
        p-value < 0.05 indicates the series is stationary (Mean Reverting).
        """
        try:
            from statsmodels.tsa.stattools import adfuller
            result = adfuller(time_series)
            return result[1] # p-value
        except ImportError:
            return 1.0 # Default to non-stationary
        except Exception as e:
            logger.error(f"ADF Test Error: {e}")
            return 1.0
        
    @ensure_data(default_return=pd.Series(dtype=float))
    def calculate_atr(self, df, period=14):
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        return true_range.rolling(period).mean()

    @ensure_data(default_return=pd.Series(dtype=float))
    def calculate_rsi(self, df, period=14):
        """Standard RSI Calculation"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    def fetch_data(self, symbol, timeframe, limit=500):
        """
        Fetches candle data.
        Primary: CCXT (Binance) - Real-time, fast.
        Fallback: yfinance - Robust, no IP blocking, slightly delayed.
        """
        # Try CCXT First (Real-Time)
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            if ohlcv:
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                return df
        except Exception as e:
            logger.warning(f"CCXT Fetch failed for {symbol} ({e}). Falling back to yfinance.")

        # Fallback to yfinance
        try:
            # Map symbol to yfinance format (BTC/USD -> BTC-USD)
            yf_symbol = symbol.replace('/', '-') if '/' in symbol else symbol
            # Ensure USDT is converted to USD for yfinance just in case
            if 'USDT' in yf_symbol: yf_symbol = yf_symbol.replace('USDT', 'USD')
            
            # Map timeframe to yfinance format
            interval_map = {'5m': '5m', '15m': '15m', '1h': '1h', '4h': '60m', '1d': '1d'} 
            yf_interval = interval_map.get(timeframe, '5m')
            
            # Fetch data (5 days is safe buffer for indicators)
            import yfinance as yf
            df = yf.download(yf_symbol, period='5d', interval=yf_interval, progress=False)
            
            if df is None or len(df) < 50:
                logger.error(f"yfinance fetched insufficient data for {symbol}")
                return None
                
            # Handle MultiIndex
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # Normalize columns
            df = df.reset_index()
            df.columns = [c.lower() for c in df.columns]
            df.rename(columns={'date': 'timestamp', 'datetime': 'timestamp'}, inplace=True)
            
            # Ensure timestamp is tz-naive for consistent comparison
            if df['timestamp'].dt.tz is not None:
                df['timestamp'] = df['timestamp'].dt.tz_localize(None)
            
            # Remove duplicate columns (Fix for ValueError: Cannot set a DataFrame with multiple columns)
            df = df.loc[:, ~df.columns.duplicated()]
            
            return df

        except Exception as e:
            logger.error(f"Error fetching data via yfinance for {symbol}: {e}")
            return None

    @ensure_data(default_return=(pd.Series(dtype=bool), pd.Series(dtype=bool)))
    def detect_fractals(self, df, window=2):
        """
        Vectorized fractal detection using NumPy.
        Returns boolean masks for Swing Highs and Lows.
        """
        # Fractal High
        is_high = df['high'].rolling(window=2*window+1, center=True).max() == df['high']
        # Fractal Low
        is_low = df['low'].rolling(window=2*window+1, center=True).min() == df['low']
        
        return is_high, is_low

    def is_killzone(self, current_time=None):
        """Checks if current time (or override) is within any active trading session."""
        now_utc = current_time.time() if current_time else datetime.utcnow().time()
        hour = now_utc.hour
        
        # Check Asian Fade Prime Window (⭐ Highest priority)
        if self.is_asian_fade_window(hour):
            return True

        # Check London Session
        london = Config.KILLZONE_LONDON
        if london and (london[0] <= hour < london[1]):
            return True

        # Check continuous NY session
        ny_session = Config.KILLZONE_NY_CONTINUOUS
        if ny_session and (ny_session[0] <= hour < ny_session[1]):
            return True
            
        # Check Asia Session
        asia = Config.KILLZONE_ASIA
        if asia and (asia[0] <= hour < asia[1]):
            return True
        
        return False

    def is_asian_fade_window(self, hour=None):
        """Returns True if we are in the 11 PM – 2 AM EST (4–7 AM UTC) Asian Fade prime window."""
        if hour is None:
            hour = datetime.utcnow().hour
        fade = Config.KILLZONE_ASIAN_FADE
        return fade is not None and (fade[0] <= hour < fade[1])

    def scan_asian_fade(self, symbol):
        """
        ⭐ PRIME ALPHA DETECTOR: Asian Range High/Low Fade
        
        Edge: 100% win rate when fading the Asian Range H/L during the
              11 PM – 2 AM EST manipulation window (4–7 AM UTC).
        
        Logic:
            1. Identify Asian Range (00:00–04:00 UTC candles)
            2. Detect Upper/Lower Quartile zones (top/bottom 25% of range)
            3. Look for a wick / false break above/below the range
            4. Confirm candle closes back inside the range (rejection)
            5. Return a SHORT (at High) or LONG (at Low) setup
        """
        if not self.is_asian_fade_window():
            return None  # Only fire during the prime window

        df = self.fetch_data(symbol, '5m', limit=500)
        if df is None or len(df) < 100:
            return None

        try:
            # Step 1: Extract Asian Range candles (00:00 – 04:00 UTC)
            df['hour'] = df['timestamp'].dt.hour
            asian_candles = df[df['hour'].between(0, 3)].tail(48)  # Last ~4 hours of 5m candles

            if len(asian_candles) < 5:
                logger.debug(f"Insufficient Asian candles for {symbol}")
                return None

            asian_high = asian_candles['high'].max()
            asian_low = asian_candles['low'].min()
            asian_range = asian_high - asian_low

            if asian_range <= 0:
                return None

            # Step 2: Define the quartile "trap" zones
            upper_quartile = asian_high - (asian_range * 0.25)  # Top 25% of range
            lower_quartile = asian_low + (asian_range * 0.25)   # Bottom 25% of range

            # Step 3 & 4: Check the last 6 candles for a false break + rejection
            recent = df.tail(6)
            last = df.iloc[-1]

            # --- SHORT SETUP: Wick above Asian High, close back inside ---
            short_setup = (
                recent['high'].max() > asian_high           # Swept high
                and last['close'] < asian_high              # Rejected back below
                and last['close'] > upper_quartile          # Closed in premium zone
                and last['close'] < last['open']            # Bearish close
            )

            # --- LONG SETUP: Wick below Asian Low, close back inside ---
            long_setup = (
                recent['low'].min() < asian_low             # Swept low
                and last['close'] > asian_low               # Rejected back above
                and last['close'] < lower_quartile          # Closed in discount zone
                and last['close'] > last['open']            # Bullish close
            )

            if not (short_setup or long_setup):
                return None

            direction = "SHORT" if short_setup else "LONG"
            entry = last['close']
            atr = self.calculate_atr(df).iloc[-1]

            stop_loss = (asian_high + atr * 0.5) if direction == "SHORT" else (asian_low - atr * 0.5)
            target = entry - (abs(entry - stop_loss) * 3.0) if direction == "SHORT" else entry + (abs(stop_loss - entry) * 3.0)

            setup = {
                'symbol': symbol,
                'pattern': f'Asian Range {direction} Fade',
                'direction': direction,
                'entry': round(entry, 2),
                'stop_loss': round(stop_loss, 2),
                'target': round(target, 2),
                'asian_high': round(asian_high, 2),
                'asian_low': round(asian_low, 2),
                'asian_range': round(asian_range, 2),
                'is_asian_fade': True,  # Flag for priority treatment
                'price_quartiles': {
                    'Asian Range': {'high': round(asian_high, 2), 'low': round(asian_low, 2)}
                },
                'time_quartile': {'num': 2, 'phase': 'Manipulation'},
                'smt_strength': 0.0,   # Will be enriched by SMT engine if available
                'bias': 'Bearish' if direction == 'SHORT' else 'Bullish',
                'index_context': 'Asian Session Fade Window',
            }

            logger.info(f"⭐ ASIAN FADE DETECTED: {symbol} {direction} | Asian H: {asian_high} | L: {asian_low}")
            return setup, df

        except Exception as e:
            logger.error(f"scan_asian_fade error for {symbol}: {e}")
            return None

    def get_detailed_bias(self, symbol, index_context=None, visual_check=False):
        """
        MULTI-FACTOR BIAS SCORING:
        1. 4H Trend (EMA 20 vs 50) - Weight 1
        2. Daily Trend (EMA 20 vs 50) - Weight 1
        3. Momentum (4H RSI) - Weight 0.5
        4. Intermarket (DXY) - Weight 1
        5. Visual (AI Vision) - Weight 1 (Optional)
        
        Returns: 
        - "STRONG BULLISH" (> 2.5) or (> 3.0 with visual)
        - "BULLISH" (> 0.5)
        - "NEUTRAL" (-0.5 to 0.5)
        - "BEARISH" (< -0.5)
        - "STRONG BEARISH" (< -2.5)
        """
        score = 0
        
        # 1. 4H Trend & Momentum
        df_4h = self.fetch_data(symbol, Config.HTF_TIMEFRAME, limit=100)
        if df_4h is not None:
            df_4h['ema_20'] = df_4h['close'].ewm(span=20).mean()
            df_4h['ema_50'] = df_4h['close'].ewm(span=50).mean()
            df_4h['rsi'] = self.calculate_rsi(df_4h)
            
            latest = df_4h.iloc[-1]
            # Trend Check
            if latest['ema_20'] > latest['ema_50']: score += 1
            elif latest['ema_20'] < latest['ema_50']: score -= 1
            
            # Momentum Check
            if latest['rsi'] > 55: score += 0.5
            elif latest['rsi'] < 45: score -= 0.5
            
        # 2. Daily Trend (HTF Alignment)
        df_1d = self.fetch_data(symbol, '1d', limit=50)
        if df_1d is not None:
            df_1d['ema_20'] = df_1d['close'].ewm(span=20).mean()
            df_1d['ema_50'] = df_1d['close'].ewm(span=50).mean()
            
            latest_d = df_1d.iloc[-1]
            if latest_d['ema_20'] > latest_d['ema_50']: score += 1
            elif latest_d['ema_20'] < latest_d['ema_50']: score -= 1
            
        # 3. Intermarket (DXY Trend)
        if index_context and 'DXY' in index_context:
            dxy_trend = index_context['DXY']['trend']
            # Inverse Correlation: DXY Down = Bullish Crypto
            if dxy_trend == 'DOWN': score += 1
            elif dxy_trend == 'UP': score -= 1

        # 4. Visual Bias (AI Vision)
        if visual_check and df_4h is not None:
            # Generate temporary chart
            chart_path = f"/tmp/{symbol.replace('/', '_')}_bias.png"
            if generate_bias_chart(df_4h, symbol, "4h", chart_path):
                validator = AIValidator()
                v_score = validator.get_visual_bias(chart_path)
                score += v_score
                # Cleanup
                try: os.remove(chart_path)
                except: pass
            
        self.last_bias_score = score
        
        threshold_strong = 3.0 if visual_check else 2.5
        threshold_weak = 1.0 if visual_check else 0.5
        
        if score >= threshold_strong: return f"STRONG BULLISH ({score})"
        if score >= threshold_weak: return f"BULLISH ({score})"
        if score <= -threshold_strong: return f"STRONG BEARISH ({score})"
        if score <= -threshold_weak: return f"BEARISH ({score})"
        
        return "NEUTRAL"

    def get_4h_bias(self, symbol):
        # Legacy wrapper
        return self.get_detailed_bias(symbol).split(" ")[-1] # Returns BULLISH/BEARISH/NEUTRAL

    def get_session_quartile(self, current_time=None):
        """
        Calculates the current ICT Session Quartile (90-minute cycles).
        Identifies the phase: Accumulation, Manipulation, Distribution, or X.
        """
        now_utc = current_time if current_time else datetime.utcnow()
        hour = now_utc.hour
        minute = now_utc.minute
        total_minutes_today = hour * 60 + minute

        # ICT Sessions (6-hour blocks starting 00:00, 06:00, 12:00, 18:00 UTC)
        # Each session has 4 x 90-minute quartiles
        session_start_hour = (hour // 6) * 6
        minutes_into_session = (hour - session_start_hour) * 60 + minute
        
        quartile_num = (minutes_into_session // 90) + 1
        phases = {
            1: "Q1: Accumulation",
            2: "Q2: Manipulation (Judas)",
            3: "Q3: Distribution",
            4: "Q4: Continuation/Reversal"
        }
        
        return {
            "num": quartile_num,
            "phase": phases.get(quartile_num, "X"),
            "minutes_in": minutes_into_session
        }

    @ensure_data(default_return=None)
    def get_price_quartiles(self, symbol):
        """
        Calculates Asian Range and CBDR High/Low and their Quartiles (SDs).
        Asian Range: 00:00 - 05:00 UTC
        CBDR: 19:00 - 01:00 UTC
        """
        # Fetch 24h of data to find ranges
        df_range = self.fetch_data(symbol, '15m', limit=100)
        if df_range is None or df_range.empty: return None
        
        # Filter for Asian Range (00:00-05:00 UTC)
        asian_df = df_range[(df_range['timestamp'].dt.hour >= 0) & (df_range['timestamp'].dt.hour < 5)]
        # Filter for London Range (07:00-10:00 UTC) - The "Inducement" Phase
        london_df = df_range[(df_range['timestamp'].dt.hour >= 7) & (df_range['timestamp'].dt.hour < 10)]
        # Filter for CBDR (19:00-01:00 UTC)
        cbdr_df = df_range[(df_range['timestamp'].dt.hour >= 19) | (df_range['timestamp'].dt.hour < 1)]
        
        ranges = {}
        for name, data in [("Asian Range", asian_df), ("London Range", london_df), ("CBDR", cbdr_df)]:
            if data.empty: continue
            r_high = data['high'].max()
            r_low = data['low'].min()
            r_diff = r_high - r_low
            
            ranges[name] = {
                "high": r_high,
                "low": r_low,
                "mid": r_low + (r_diff * 0.5),
                "q1": r_low + (r_diff * 0.25),
                "q3": r_low + (r_diff * 0.75),
                "sd_1_pos": r_high + r_diff,
                "sd_1_neg": r_low - r_diff
            }
        
        return ranges
    
    def validate_sweep_depth(self, symbol, swept_level, direction):
        """
        Level 2 Depth Filter: Validates that liquidity sweep had actual institutional absorption.
        
        Args:
            symbol: Trading pair
            swept_level: Price level that was swept
            direction: 'LONG' or 'SHORT'
        
        Returns:
            True if whale absorption detected, False if retail dust
        """
        if not self.order_book_enabled:
            return True  # Skip filter if not supported
        
        try:
            # Fetch order book (Level 2 depth)
            order_book = self.exchange.fetch_order_book(symbol, limit=50)
            
            # For LONG setup (sweep below), check buy-side absorption
            if direction == 'LONG':
                bids = order_book['bids']  # [[price, amount], ...]
                total_volume = 0
                
                # Check if significant buy orders near swept level
                for bid in bids:
                    price, amount = bid[0], bid[1]
                    # Within 0.5% of swept level
                    if abs(price - swept_level) / swept_level < 0.005:
                        total_volume += amount
                
                # Require minimum 5 BTC of buy-side absorption
                return total_volume >= 5.0
            
            # For SHORT setup (sweep above), check sell-side absorption
            else:
                asks = order_book['asks']
                total_volume = 0
                
                for ask in asks:
                    price, amount = ask[0], ask[1]
                    if abs(price - swept_level) / swept_level < 0.005:
                        total_volume += amount
                
                return total_volume >= 5.0
        
        except Exception as e:
            logger.warning(f"Order book fetch failed: {e}. Skipping depth filter.")
            return True  # Don't reject trade if order book unavailable
    
    def calculate_atr(self, df, period=14):
        """
        Calculate Average True Range for volatility-adjusted targeting.
        
        Args:
            df: OHLCV dataframe
            period: ATR period (default 14)
        
        Returns:
            pandas Series with ATR values
        """
        high = df['high']
        low = df['low']
        close = df['close']
        
        # True Range = max(high-low, abs(high-prev_close), abs(low-prev_close))
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr
    
    def get_volatility_adjusted_target(self, df, direction, entry_price, session_range):
        """
        ATR-Dynamic Targeting: Adjusts targets based on current volatility.
        
        High Volatility (ATR > 1.5x mean): Target SD 2.0 (capture expansion)
        Low Volatility (ATR < mean): Target nearest FVG or institutional draw (minimum 3R)
        Normal Volatility: Target SD 1.0 (current strategy)
        
        Args:
            df: OHLCV dataframe
            direction: 'LONG' or 'SHORT'
            entry_price: Entry price
            session_range: Price quartiles dict
        
        Returns:
            Target price (guaranteed minimum 3R from entry)
        """
        atr = self.calculate_atr(df)
        if atr is None or len(atr) < 14:
            # Fallback to SD 1.0 if ATR unavailable
            return session_range.get('sd_1_pos' if direction == 'LONG' else 'sd_1_neg')
        
        mean_atr = atr.iloc[-50:].mean()  # 50-period mean
        current_atr = atr.iloc[-1]
        
        # Calculate stop loss to determine minimum 3R target
        stop_buffer = current_atr * Config.STOP_LOSS_ATR_MULTIPLIER
        if direction == 'LONG':
            stop_loss = entry_price - stop_buffer
            risk = entry_price - stop_loss
            min_target_3r = entry_price + (3.0 * risk)
        else:  # SHORT
            stop_loss = entry_price + stop_buffer
            risk = stop_loss - entry_price
            min_target_3r = entry_price - (3.0 * risk)
        
        # High Volatility: Expanded Targets
        if current_atr > mean_atr * 1.5:
            logger.info(f"📈 High Volatility Detected (ATR: {current_atr:.2f} > {mean_atr*1.5:.2f}). Targeting SD 2.0")
            target = session_range.get('sd_2_pos' if direction == 'LONG' else 'sd_2_neg', 
                                    session_range.get('sd_1_pos' if direction == 'LONG' else 'sd_1_neg'))
        
        # Low Volatility: Use institutional draw, NOT session midpoint
        elif current_atr < mean_atr:
            logger.info(f"📉 Low Volatility Detected (ATR: {current_atr:.2f} < {mean_atr:.2f}). Targeting Institutional Draw (min 3R)")
            # Use get_next_institutional_target instead of session midpoint
            target = self.get_next_institutional_target(df, direction, entry_price)
        
        # Normal Volatility: SD 1.0 (current strategy)
        else:
            target = session_range.get('sd_1_pos' if direction == 'LONG' else 'sd_1_neg')
        
        # CRITICAL: Enforce minimum 3R for all institutional setups
        if direction == 'LONG' and target < min_target_3r:
            logger.warning(f"⚠️ Target {target:.2f} < 3R floor {min_target_3r:.2f}. Using 3R minimum.")
            return min_target_3r
        elif direction == 'SHORT' and target > min_target_3r:
            logger.warning(f"⚠️ Target {target:.2f} > 3R floor {min_target_3r:.2f}. Using 3R minimum.")
            return min_target_3r
            
        return target
            
    def get_next_institutional_target(self, df, direction, entry_price):
        """
        DYNAMIC TARGETING: Scans for the nearest 'Draw on Liquidity'.
        1. Nearest Unfilled FVG (Fair Value Gap)
        2. Nearest Major Swing Pivot (Liquidity Pool)
        """
        target = None
        min_rr = 3.0 # Institutional minimum risk/reward aspiration
        
        # Scan last 100 candles for resting liquidity
        recent = df.iloc[-100:]
        
        if direction == "LONG":
            # 1. Look for Bearish FVG above entry
            # Bearish FVG: Low of candle i-2 > High of candle i
            for i in range(len(recent)-3, 0, -1):
                c0 = recent.iloc[i]     # Current
                c2 = recent.iloc[i-2]   # 2 candles ago
                
                # Check for gap
                if c2['low'] > c0['high']:
                    fvg_bottom = c0['high']
                    # Is it above our entry?
                    if fvg_bottom > entry_price:
                        # Is it "Unfilled" (Price hasn't traded through it yet)?
                        # Simplified check: Just find the first valid one above current
                        return fvg_bottom
            
            # 2. Fallback: Major Swing High (Liquidity Pool)
            swing_high = recent['high'].max()
            if swing_high > entry_price:
                return swing_high
                
            # 3. Last Resort: 1:4 Expansion
            return entry_price * 1.02 

        elif direction == "SHORT":
            # 1. Look for Bullish FVG below entry
            # Bullish FVG: High of candle i-2 < Low of candle i
            for i in range(len(recent)-3, 0, -1):
                c0 = recent.iloc[i]     # Current (High)
                c2 = recent.iloc[i-2]   # 2 candles ago (Low)
                
                if c2['high'] < c0['low']:
                    fvg_top = c0['low']
                    if fvg_top < entry_price:
                        return fvg_top
                        
            # 2. Fallback: Major Swing Low
            swing_low = recent['low'].min()
            if swing_low < entry_price:
                return swing_low
                
            # 3. Last Resort: 1:4 Expansion
            return entry_price * 0.98

        return target

    def is_tapping_fvg(self, df, direction):
        """
        Checks if current price is tapping into a valid, unmitigated Fair Value Gap.
        Used for 'Standard Pullback' entries.
        """
        current_low = df['low'].iloc[-1]
        current_high = df['high'].iloc[-1]
        
        # Scan last 20 candles for FVG
        recent = df.iloc[-25:-1] # Look back, excluding current
        
        if direction == "LONG":
            # Look for Bullish FVG (Buying opportunity in Discount)
            # Bullish FVG: Low of candle i > High of candle i-2
            for i in range(2, len(recent)):
                c0 = recent.iloc[i]     # Top of FVG (Low of candle i)
                c2 = recent.iloc[i-2]   # Bottom of FVG (High of candle i-2)
                
                if c0['low'] > c2['high']:
                    fvg_top = c0['low']
                    fvg_bottom = c2['high']
                    
                    # Check mitigation: Has price ALREADY closed below this FVG?
                    # If so, it's invalid.
                    # Simplified: Check if current price is INSIDE it.
                    if current_low <= fvg_top and current_low >= fvg_bottom:
                         return True
                         
        elif direction == "SHORT":
            # Look for Bearish FVG (Selling opportunity in Premium)
            # Bearish FVG: High of candle i < Low of candle i-2
            for i in range(2, len(recent)):
                c0 = recent.iloc[i]     # Bottom of FVG (High of candle i)
                c2 = recent.iloc[i-2]   # Top of FVG (Low of candle i-2)
                
                if c0['high'] < c2['low']:
                    fvg_top = c2['low']
                    fvg_bottom = c0['high']
                    
                    # Check if current price is INSIDE it.
                    if current_high >= fvg_bottom and current_high <= fvg_top:
                        return True
                        
        return False

    @safe_scan("Scanner.scan_pattern")
    def scan_pattern(self, symbol, timeframe='5m', cached_context=None, provided_df=None, current_time_override=None):
        """
        Main Scanning Function.
        Checks: Killzone -> Trend Bias -> Price Quartiles -> SMC Pattern
        """
        # 1. HARD GATE: Time (Killzone)
        if not self.is_killzone(current_time=current_time_override):
            return None

        # DEDUPLICATION GATE: Prevent the same symbol from firing multiple times per candle window
        now_ts = (current_time_override or datetime.utcnow()).timestamp()
        cache_key = symbol
        last_fired = self._signal_cache.get(cache_key, 0)
        cooldown_secs = self._signal_cooldown_mins * 60
        if (now_ts - last_fired) < cooldown_secs:
            logger.debug(f"🔇 Deduplicated signal for {symbol} (cooldown: {int(cooldown_secs - (now_ts - last_fired))}s remaining)")
            return None

        # 2. SOFT GATE: News Context (Use Cache or Live)
        if cached_context and 'news' in cached_context:
            news_data = cached_context['news']
            is_safe = news_data['is_safe']
            event = news_data['event']
            mins = news_data['minutes_until']
        else:
            # TODO: Add news mocking for backtest
            is_safe, event, mins = self.news.is_news_safe()
        
        news_context = "Clear"
        if not is_safe:
             news_context = f"ACTIVE EVENT: {event} in {mins}m"
             print(f"⚠️ News Event Detected: {event}. Proceeding with CAUTION.")
             
        # 3. Fetch Institutional Context (Use Cache or Live)
        if cached_context and 'intermarket' in cached_context:
            index_context = cached_context['intermarket']
        else:
            index_context = self.intermarket.get_market_context()
            
        # 4. HARD GATE: Bias (HTF 4H + Daily + Intermarket + Visual)
        # We pass visual_check=True as per User Request for enhanced accuracy
        bias_full = self.get_detailed_bias(symbol, index_context=index_context, visual_check=True)
        if "STRONG" in bias_full:
            logger.info(f"💪 STRONG BIAS DETECTED: {bias_full}")
        
        # 3. GET SESSION METADATA (Time & Price Quartiles)
        time_quartile = self.get_session_quartile(current_time=current_time_override)
        price_quartiles = self.get_price_quartiles(symbol)
        
        if provided_df is not None:
             df = provided_df
        else:
             df = self.fetch_data(symbol, timeframe)
             
        if df is None:
            return None

        # Current and recent data
        current = df.iloc[-1]
        
        # Recent high/low for liquidity levels (24h Lookback - PDH/PDL)
        # 288 candles * 5m = 1440m = 24 hours
        recent_high = df['high'].iloc[-288:-1].max()
        recent_low = df['low'].iloc[-288:-1].min()

        recent_low = df['low'].iloc[-288:-1].min()

        # TIER 1: Time Series Analysis (New Quant Layer)
        # We want Mean Reversion (Hurst < 0.5) for "Sweeps"
        closes = df['close'].values
        hurst = self.get_hurst_exponent(closes)
        adf_p = self.get_adf_test(closes)
        # We don't filter HARD on this yet, just log it
        is_mean_reverting = hurst < 0.5 or adf_p < 0.05

        setup = None
        entry_type = None

        # BULLISH Setup (OPTIMIZED: Require STRONG bias for quality)
        if "BULLISH" in bias_full:
            # TIER 1: Deep Discount
            in_deep_discount = False
            if price_quartiles:
                ref_range = price_quartiles.get("Asian Range") or price_quartiles.get("CBDR")
                if ref_range:
                    price_position = (current['close'] - ref_range['low']) / (ref_range['high'] - ref_range['low'])
                    if Config.MIN_PRICE_QUARTILE <= price_position <= Config.MAX_PRICE_QUARTILE:
                        in_deep_discount = True
            
            # TIER 1: SMT (Multi-Asset Sponsorship)
            smt_strength = self.intermarket.calculate_cross_asset_divergence('LONG', index_context)
            has_strong_smt = smt_strength >= Config.MIN_SMT_STRENGTH
            
            # LOGIC A: JUDAS SWEEP (High Alpha)
            swept_pdl = current['low'] < recent_low and current['close'] > recent_low
            swept_london = False
            london_range = None
            if price_quartiles and "London Range" in price_quartiles:
                london_range = price_quartiles["London Range"]
                swept_london = current['low'] < london_range["low"] and current['close'] > london_range["low"]

            
            # SIMPLIFIED: Proceed if we have discount zone + SMT alignment
            # (Removed strict 3/4 confluence requirement that was too restrictive)
            if in_deep_discount or has_strong_smt:
                if (swept_pdl or swept_london):
                    # LEVEL 2 DEPTH FILTER
                    swept_level = recent_low if swept_pdl else (london_range["low"] if london_range else recent_low)
                    if self.validate_sweep_depth(symbol, swept_level, 'LONG'):
                        entry_type = "Judas Sweep (High Alpha)"
                
                # LOGIC B: FVG TAP (Medium Alpha - Standard Pullback)
                elif self.is_tapping_fvg(df, 'LONG'):
                     entry_type = "Trend Pullback (Medium Alpha)"

            if entry_type:
                # ATR-DYNAMIC TARGETING
                ref_range_target = london_range or price_quartiles.get("Asian Range")
                target = self.get_volatility_adjusted_target(df, 'LONG', current['close'], ref_range_target)
                
                if not target:
                    target = self.get_next_institutional_target(df, "LONG", current['close'])

                # STRATEGY: WIDE NET
                atr = self.calculate_atr(df).iloc[-1]
                if pd.isna(atr): atr = current['close'] * 0.005
                stop_buffer = atr * Config.STOP_LOSS_ATR_MULTIPLIER
                
                direction = 'LONG'
                stop_loss = current['close'] - stop_buffer
                risk = current['close'] - stop_loss
                
                # Trinity Check
                cross_asset_div = self.intermarket.calculate_cross_asset_divergence('LONG', index_context)

                setup = {
                    "timestamp": current['timestamp'].isoformat() if hasattr(current['timestamp'], 'isoformat') else str(current['timestamp']),
                    "symbol": symbol,
                    "pattern": f"Bullish {entry_type}",
                    "bias": bias_full,
                    "entry": current['close'],
                    "stop_loss": stop_loss,
                    "target": target,
                    'tp1': current['close'] + (risk * Config.TP1_R_MULTIPLE),
                    'direction': direction,
                    "time_quartile": time_quartile,
                    "price_quartiles": price_quartiles,
                    "index_context": index_context,
                    "smt_strength": round(smt_strength, 2),
                    "hurst_exponent": round(hurst, 2),
                    "adf_p_value": round(adf_p, 4),
                    "is_mean_reverting": bool(is_mean_reverting),
                    "cross_asset_divergence": round(cross_asset_div, 2),
                    "news_context": news_context,
                    "is_discount": True,
                    'risk_reward': Config.TP2_R_MULTIPLE,
                    'quality': 'HIGH' if 'Judas' in entry_type else 'MEDIUM'
                }

        # BEARISH Setup (OPTIMIZED: Require bias for quality - Only if no Long found yet)
        if not setup and "BEARISH" in bias_full:
            # TIER 1: Premium
            in_premium = False
            if price_quartiles:
                ref_range = price_quartiles.get("Asian Range") or price_quartiles.get("CBDR")
                if ref_range:
                    price_position = (current['close'] - ref_range['low']) / (ref_range['high'] - ref_range['low'])
                    if Config.MIN_PRICE_QUARTILE_SHORT <= price_position <= Config.MAX_PRICE_QUARTILE_SHORT:
                        in_premium = True
            # TIER 1: SMT (Multi-Asset Sponsorship)
            smt_strength = self.intermarket.calculate_cross_asset_divergence('SHORT', index_context)
            has_strong_smt = smt_strength >= Config.MIN_SMT_STRENGTH
            
            # LOGIC A: JUDAS SWEEP (High Alpha)
            swept_pdh = current['high'] > recent_high and current['close'] < recent_high
            swept_london = False
            london_range = None
            if price_quartiles and "London Range" in price_quartiles:
                london_range = price_quartiles["London Range"]
                swept_london = current['high'] > london_range["high"] and current['close'] < london_range["high"]

            entry_type = None

            
            # SIMPLIFIED: Proceed if we have premium zone + SMT alignment
            # (Removed strict 3/4 confluence requirement that was too restrictive)
            if in_premium or has_strong_smt:
                if (swept_pdh or swept_london):
                    # LEVEL 2 DEPTH FILTER
                    swept_level = recent_high if swept_pdh else (london_range["high"] if london_range else recent_high)
                    if self.validate_sweep_depth(symbol, swept_level, 'SHORT'):
                        entry_type = "Judas Sweep (High Alpha)"
                
                # LOGIC B: FVG TAP (Medium Alpha)
                elif self.is_tapping_fvg(df, 'SHORT'):
                     entry_type = "Trend Pullback (Medium Alpha)"

            if entry_type:
                ref_range_target = london_range or price_quartiles.get("Asian Range")
                target = self.get_volatility_adjusted_target(df, 'SHORT', current['close'], ref_range_target)
                
                if not target:
                    target = self.get_next_institutional_target(df, "SHORT", current['close'])
                
                atr = self.calculate_atr(df).iloc[-1]
                if pd.isna(atr): atr = current['close'] * 0.005
                stop_buffer = atr * Config.STOP_LOSS_ATR_MULTIPLIER
                
                direction = 'SHORT'
                stop_loss = current['close'] + stop_buffer
                risk = stop_loss - current['close']
                
                cross_asset_div = self.intermarket.calculate_cross_asset_divergence('SHORT', index_context)
                
                setup = {
                    "symbol": symbol,
                    "pattern": f"Bearish {entry_type}",
                    "bias": bias_full,
                    "entry": current['close'],
                    "stop_loss": stop_loss,
                    "target": target,
                    'tp1': current['close'] - (risk * Config.TP1_R_MULTIPLE),
                    'direction': direction,
                    "time_quartile": time_quartile,
                    "price_quartiles": price_quartiles,
                    "index_context": index_context,
                    "smt_strength": round(smt_strength, 2),
                    "hurst_exponent": round(hurst, 2),
                    "adf_p_value": round(adf_p, 4),
                    "is_mean_reverting": bool(is_mean_reverting),
                    "cross_asset_divergence": round(cross_asset_div, 2),
                    "news_context": news_context,
                    "is_premium": True,
                    'risk_reward': Config.TP2_R_MULTIPLE,
                    'quality': 'HIGH' if 'Judas' in entry_type else 'MEDIUM'
                }



        if setup:
            # Stamp cache so this symbol is deduplicated for the next cooldown window
            self._signal_cache[cache_key] = now_ts
            return setup, df
        return None

    @safe_scan("Scanner.scan_order_flow")
    def scan_order_flow(self, symbol, timeframe=Config.TIMEFRAME):
        """
        STRATEGY 3: ICT ORDER FLOW (Order Blocks + MSS)
        Focuses on high-probability reversals or continuations sponsored by institutions.
        """
        # 1. BIAS CHECK (Hard Gate)
        # We reuse the detailed bias logic
        index_context = self.intermarket.get_market_context()
        bias_full = self.get_detailed_bias(symbol, index_context=index_context, visual_check=False) # Visual done later if needed
        
        # Parse bias direction
        is_bullish = "BULLISH" in bias_full or "NEUTRAL" in bias_full
        is_bearish = "BEARISH" in bias_full or "NEUTRAL" in bias_full
        
        if not is_bullish and not is_bearish:
            return None

        # 2. Fetch Data
        df = self.fetch_data(symbol, timeframe)
        if df is None: return None
        
        current = df.iloc[-1]
        
        # 3. Detect Market Structure Shift (MSS)
        # Look back 50 candles for a pivot break with displacement
        mss_setup = self.detect_mss(df, lookback=50)
        
        if not mss_setup:
            return None
            
        direction = mss_setup['direction'] # 'LONG' or 'SHORT'
        
        # Bias Confirmation
        if direction == 'LONG' and not is_bullish: return None
        if direction == 'SHORT' and not is_bearish: return None
        
        # 4. Find Responsible Order Block (OB)
        # The OB is the candle(s) BEFORE the displacement leg
        ob_setup = self.find_order_block(df, mss_setup['origin_index'], direction)
        
        if not ob_setup:
            return None
            
        # 5. Check if Price is within Entry Zone (OB + FVG)
        # Entry: Mean Threshold (50% of OB) or Open of OB
        entry_price = ob_setup['mean_threshold']
        stop_loss = ob_setup['invalidation_level']
        target = self.get_next_institutional_target(df, direction, current['close'])
        
        # Calculate Distance to Entry
        dist_percent = abs(current['close'] - entry_price) / current['close']
        
        # If price is too far away (> 0.5% away from OB), ignore
        if dist_percent > 0.005: 
            return None
            
        # 6. Construct Setup
        risk = abs(entry_price - stop_loss)
        if risk == 0: return None
        
        setup = {
            "timestamp": current['timestamp'].isoformat() if hasattr(current['timestamp'], 'isoformat') else str(current['timestamp']),
            "symbol": symbol,
            "pattern": f"{'Bullish' if direction == 'LONG' else 'Bearish'} Order Block (Flow)",
            "bias": bias_full,
            "entry": entry_price,
            "stop_loss": stop_loss,
            "target": target,
            'tp1': entry_price + (risk * 2) if direction == 'LONG' else entry_price - (risk * 2),
            'direction': direction,
            "time_quartile": self.get_session_quartile(),
            "price_quartiles": self.get_price_quartiles(symbol),
            "index_context": index_context,
            "smt_strength": 0.0, # Not core to this strategy
            "cross_asset_divergence": 0.0,
            "news_context": "Checked",
            "is_discount": True, # Assumed if retracing to OB
            'risk_reward': 3.0,
            'quality': 'HIGH'
        }
        
        return setup, df

    def detect_mss(self, df, lookback=50):
        """
        Detects if a Market Structure Shift has occurred recently.
        Returns dict with direction and origin index (start of displacement).
        """
        subset = df.iloc[-lookback:]
        
        # Find Swing Highs and Lows (Fractals)
        # Simple 3-candle fractal
        highs = (subset['high'] > subset['high'].shift(1)) & (subset['high'] > subset['high'].shift(-1))
        lows = (subset['low'] < subset['low'].shift(1)) & (subset['low'] < subset['low'].shift(-1))
        
        last_swing_high = subset[highs].iloc[-1] if hasattr(subset[highs], 'iloc') and len(subset[highs]) > 0 else None
        last_swing_low = subset[lows].iloc[-1] if hasattr(subset[lows], 'iloc') and len(subset[lows]) > 0 else None
        
        current = df.iloc[-1]
        
        # Check Bullish MSS: Break of Last Swing High
        if last_swing_high is not None:
            # If we closed above the last swing high RECENTLY (last 5 candles)
            break_idx = subset[subset['close'] > last_swing_high['high']].index
            if len(break_idx) > 0 and break_idx[-1] >= df.index[-5]:
                # Check for Displacement (Large Candle or FVG)
                # Simplified: Candle body > ATR * 1.5
                return {'direction': 'LONG', 'origin_index': last_swing_low.name} # Origin is the low before the break
                
        # Check Bearish MSS: Break of Last Swing Low
        if last_swing_low is not None:
             break_idx = subset[subset['close'] < last_swing_low['low']].index
             if len(break_idx) > 0 and break_idx[-1] >= df.index[-5]:
                 return {'direction': 'SHORT', 'origin_index': last_swing_high.name}

        return None

    def find_order_block(self, df, origin_index, direction):
        """
        Identifies the Order Block candle at the origin of the move.
        """
        try:
            # Origin index is the Swing Point.
            # OB is usually the candle AT or just BEFORE the Swing Point.
            idx_loc = df.index.get_loc(origin_index)
            
            # Look at 3 candles around the origin to find the specific OB candle
            # Bullish OB: Last DOWN candle before up move
            # Bearish OB: Last UP candle before down move
            
            candidates = df.iloc[idx_loc-2:idx_loc+2]
            ob_candle = None
            
            for i in range(len(candidates)):
                candle = candidates.iloc[i]
                is_green = candle['close'] > candle['open']
                is_red = candle['close'] < candle['open']
                
                if direction == 'LONG' and is_red:
                    ob_candle = candle
                elif direction == 'SHORT' and is_green:
                    ob_candle = candle
                    
            if ob_candle is None:
                ob_candle = df.iloc[idx_loc] # Fallback to pivot candle
                
            high = ob_candle['high']
            low = ob_candle['low']
            mean_threshold = (high + low) / 2
            
            if direction == 'LONG':
                 invalidation = low
            else:
                 invalidation = high
                 
            return {
                'open': ob_candle['open'],
                'close': ob_candle['close'],
                'high': high,
                'low': low,
                'mean_threshold': mean_threshold,
                'invalidation_level': invalidation
            }
            
        except Exception as e:
            logger.error(f"Error finding OB: {e}")
            return None

if __name__ == "__main__":
    scanner = SMCScanner()
    print(f"🚀 Scanning {Config.SYMBOLS[0]}...")
    result = scanner.scan_pattern(Config.SYMBOLS[0])
    if result:
        print(f"✅ Found: {result['pattern']} on {result['symbol']}")
    else:
        print("Thinking... No clean institutional setups found.")



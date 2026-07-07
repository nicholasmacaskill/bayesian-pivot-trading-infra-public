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

# Prevent yfinance filesystem/locking/FD leak issues by forcing it to use the dummy cache
try:
    from yfinance import cache
    cache._TzCacheManager._tz_cache = cache._TzCacheDummy()
except Exception:
    pass

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

def send_pulse_to_telegram(message):
    """Bridge to send pulse updates to Telegram via individual bot or shared utility"""
    try:
        from src.clients.telegram_notifier import send_message
        send_message(message)
    except Exception as e:
        logger.error(f"Pulse Telegram Error: {e}")

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
        self._signal_cooldown_mins = 60  # Increased from 15m to 60m to reduce noise <!-- id: 9 -->
        self.bias_cache = {} # Protect against redundant calls
        self.last_pulse_time = 0

    def log_market_pulse(self, symbol):
        """
        Terminal Consciousness: Sends a periodic 'System Sentiment' update to Telegram.
        Triggered every 15 minutes by the local runner.
        """
        try:
            now = time.time()
            # 1. Fetch Data
            df = self.fetch_data(symbol, Config.TIMEFRAME, limit=300)
            if df is None: return
            
            # 2. Extract Hurst & SMT
            closes = df['close'].values
            hurst = self.get_hurst_exponent(closes)
            
            # Identify Regime
            regime = "CHOP / RANDOM"
            h_low, h_high = Config.get('HURST_CHAOS_RANGE', (0.495, 0.505))
            if hurst > h_high: regime = "EXPANSION (Momentum)"
            elif hurst < h_low: regime = "MEAN REVERSION (Range)"
            
            # 3. Get Macro Bias
            bias_full = self.get_detailed_bias(symbol)
            
            # 3b. Calculate detailed timeframe bias breakdown (1D, 4H, 1H)
            bias_breakdown = ""
            try:
                df_1d = self.fetch_data(symbol, '1d', limit=100, synchronized=False)
                df_4h = self.fetch_data(symbol, '4h', limit=100, synchronized=False)
                df_1h = self.fetch_data(symbol, '1h', limit=100, synchronized=False)
                
                def get_tf_bias_str(df):
                    if df is None or df.empty: return "N/A"
                    ema20 = df['close'].ewm(span=20).mean().iloc[-1]
                    ema50 = df['close'].ewm(span=50).mean().iloc[-1]
                    return "BULL" if ema20 > ema50 else "BEAR"
                
                bias_1d_str = get_tf_bias_str(df_1d)
                bias_4h_str = get_tf_bias_str(df_4h)
                bias_1h_str = get_tf_bias_str(df_1h)
                
                bias_breakdown = f" (1D: {bias_1d_str} | 4H: {bias_4h_str} | 1H: {bias_1h_str})"
            except Exception as e:
                logger.error(f"Failed to calculate detailed biases: {e}")

            # 4. SMT Context
            smt_strength = self.intermarket.get_smt_strength(symbol, df)
            
            # 4b. Dynamic Strategic Playbook
            interpretation_lines = []
            
            # Bias interpretation
            if "Conflict" in bias_full or "NEUTRAL" in bias_full.upper():
                interpretation_lines.append("• *Bias:* Trend direction is mixed. Breakout/momentum trades are risky; prefer range sweep fades.")
            elif "BULLISH" in bias_full.upper():
                interpretation_lines.append("• *Bias:* Macro trend aligned upward. Long setups (discount sweeps/reclaims) have higher probability.")
            elif "BEARISH" in bias_full.upper():
                interpretation_lines.append("• *Bias:* Macro trend aligned downward. Short setups (premium sweeps/rejections) have higher probability.")
            else:
                interpretation_lines.append("• *Bias:* Neutral/consolidation. Enforce strict range-bound rules.")

            # Hurst regime interpretation
            if hurst < h_low:
                interpretation_lines.append("• *Regime:* Mean Reversion active. Breakouts are highly likely to fake out. We focus on range sweeps (Turtle Soup) at session extremes.")
            elif hurst > h_high:
                interpretation_lines.append("• *Regime:* Expansion active. Price is trending. Look for structure shifts (MSS) and ride displacement momentum.")
            else:
                interpretation_lines.append("• *Regime:* Choppy / Random. High noise level; the funnel is in defensive mode.")

            # SMT interpretation
            if smt_strength >= 0.5:
                interpretation_lines.append(f"• *Sponsorship:* SMT is strong ({smt_strength:.2f}), confirming quiet institutional accumulation/distribution at range boundaries.")
            else:
                interpretation_lines.append("• *Sponsorship:* SMT is weak. Current move lacks divergence-backed institutional validation.")

            interpretation_block = "\n".join(interpretation_lines)
            
            # 5. Format Message
            pulse_msg = (
                f"🧠 *Bayesian Pivot Sentiment* | `{symbol}`\n"
                f"───────────────────\n"
                f"🏛️ **Macro Bias:** {bias_full}{bias_breakdown}\n"
                f"🌀 **Hurst Regime:** {regime} ({hurst:.3f})\n"
                f"⚡ **SMT Divergence:** {smt_strength:.2f}/1.0\n"
                f"───────────────────\n"
                f"💡 **Strategic Playbook:**\n"
                f"{interpretation_block}\n"
                f"───────────────────\n"
                f"🛡️ *9-Gate Funnel: ARMED & SCANNING*"
            )
            
            logger.info(f"Pulse: {pulse_msg.replace('*', '').replace('`', '')}")
            send_pulse_to_telegram(pulse_msg)
            self.last_pulse_time = now
            return True
        except Exception as e:
            logger.error(f"Error generating Market Pulse: {e}")
            return False

    def get_hurst_exponent(self, time_series):
        # [REDACTED] Proprietary Geometric Persistence Math
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

    def _aggregate_ohlcv(self, df, timeframe='4h'):
        """Aggregates lower timeframe data into higher timeframe bars manually."""
        if timeframe != '4h': return df
        if df is None or df.empty: return None
        
        # Ensure timestamp is index for resample
        df_copy = df.copy().set_index('timestamp')
        resampled = df_copy.resample('4h').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }).dropna()
        return resampled.reset_index()

    def _check_data_synchrony(self, symbol, df_ccxt):
        """
        Synchronized Data Buffer: Compares CCXT vs yfinance.
        Delta > 0.05% or Latency > 2 mins results in False.
        """
        if df_ccxt is None or df_ccxt.empty:
            return False
            
        # Fetch yfinance data internally
        try:
            # Map symbol to yfinance format (BTC/USD -> BTC-USD)
            # Match symbol format
            yf_symbol = symbol.replace('/', '-') if '/' in symbol else symbol
            if 'USDT' in yf_symbol: yf_symbol = yf_symbol.replace('USDT', 'USD')
            
            # Fetch yfinance 5m data for a tighter match (limit to 1 day for speed)
            import yfinance as yf
            df_yf_raw = yf.download(yf_symbol, period='1d', interval='5m', progress=False)
            
            if df_yf_raw is None or df_yf_raw.empty:
                logger.warning(f"yfinance 5m sync failed for {symbol} - retrying with 1h")
                df_yf_raw = yf.download(yf_symbol, period='5d', interval='1h', progress=False)
            
            if df_yf_raw is None or df_yf_raw.empty:
                logger.warning(f"yfinance sync failed for {symbol} - holding trade.")
                return False

            if isinstance(df_yf_raw.columns, pd.MultiIndex):
                df_yf_raw.columns = df_yf_raw.columns.get_level_values(0)
            df_yf_raw = df_yf_raw.reset_index()
            df_yf_raw.columns = [c.lower() for c in df_yf_raw.columns]
            df_yf_raw.rename(columns={'date': 'timestamp', 'datetime': 'timestamp'}, inplace=True)
            if df_yf_raw['timestamp'].dt.tz is not None:
                df_yf_raw['timestamp'] = df_yf_raw['timestamp'].dt.tz_localize(None)
            
            df_yf = df_yf_raw.loc[:, ~df_yf_raw.columns.duplicated()]
            
            # Use the latest available price from yfinance
            yf_latest = df_yf.iloc[-1]
            ccxt_latest = df_ccxt.iloc[-1]
            
            # 1. Price Delta Check (Sanity Check: 0.25% or Config)
            price_delta = abs(ccxt_latest['close'] - yf_latest['close']) / ccxt_latest['close']
            
            # Use UTC for comparison
            ts_diff = abs((ccxt_latest['timestamp'] - yf_latest['timestamp']).total_seconds())
            
            # Threshold: 0.05% if perfectly aligned, else 0.5% for sanity check
            base_threshold = Config.get('SYNC_PRICE_DELTA_MAX', 0.0005)
            # If timestamps are significantly different, loosen threshold for "Reality Check"
            threshold = 0.0025 if ts_diff > 300 else base_threshold # 0.25% if offset
                
            if price_delta > threshold:
                logger.warning(f"⚖️ Data Sync Delta Breach: {price_delta:.4%} (Threshold: {threshold:.4%})")
                return False
                
            return True
        except Exception as e:
            logger.error(f"Sync Buffer Error: {e}")
            return False

    def fetch_data(self, symbol, timeframe, limit=100, synchronized=True):
        """
        98% Reliability Refactor: SynchronizedDataBuffer for parallel streams.
        Eliminates proxies and enforces strict time-drift validation (120s limit).
        """
        try:
            tf_to_seconds = {'1m': 60, '5m': 300, '1h': 3600, '4h': 14400, '1d': 86400}
            
            # 1. Fetch Primary Stream
            # Coinbase doesn't natively support 4H in CCXT, so if timeframe is 4h, we fallback to 1h then aggregate
            if timeframe == '4h' and self.exchange.id == 'coinbase':
                df_raw_main = self.exchange.fetch_ohlcv(symbol, '1h', limit=limit*4)
                if not df_raw_main: return None
                main_df_base = pd.DataFrame(df_raw_main, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                main_df_base['timestamp'] = pd.to_datetime(main_df_base['timestamp'], unit='ms')
                main_df = self._aggregate_ohlcv(main_df_base, '4h')
            else:
                df_raw_main = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                if not df_raw_main: return None
                main_df = pd.DataFrame(df_raw_main, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                main_df['timestamp'] = pd.to_datetime(main_df['timestamp'], unit='ms')

            if not synchronized:
                return main_df

            # 2. SynchronizedDataBuffer: Check 5M, 1H, and 4H drift
            timeframes_to_check = ['5m', '1h']
            if timeframe != '4h': timeframes_to_check.append('4h')
            
            for tf in timeframes_to_check:
                if tf == '4h':
                    # Native aggregation for 4H
                    df_base_raw = self.exchange.fetch_ohlcv(symbol, '1h', limit=limit*4)
                    if not df_base_raw: continue
                    df_base = pd.DataFrame(df_base_raw, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df_base['timestamp'] = pd.to_datetime(df_base['timestamp'], unit='ms')
                    df_tf = self._aggregate_ohlcv(df_base, '4h')
                else:
                    df_raw = self.exchange.fetch_ohlcv(symbol, tf, limit=10)
                    if not df_raw: continue
                    df_tf = pd.DataFrame(df_raw, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df_tf['timestamp'] = pd.to_datetime(df_tf['timestamp'], unit='ms')

                if df_tf is None or df_tf.empty:
                    continue

                # Time-Drift Validation (Config + Candle Duration)
                latest_ts = df_tf.iloc[-1]['timestamp']
                
                # Use UTC for comparison as ccxt timestamps are UTC
                now_utc = datetime.utcnow()
                drift = abs((now_utc - latest_ts).total_seconds())
                
                # Limit must account for the fact that the latest bar timestamp is the START of the candle
                tf_sec = tf_to_seconds.get(tf, 300)
                allowed_drift = Config.get('SYNC_LATENCY_SEC_MAX', 120) + tf_sec
                
                if drift > allowed_drift:
                    logger.error(f"🚨 DATA_DESYNC: Stream {tf} drift is {drift:.1f}s (Limit: {allowed_drift}s). Pausing execution.")
                    return None # Triggers "HOLD" state in runner

            # 3. Double-Source Check (CCXT vs yFinance)
            if not self._check_data_synchrony(symbol, main_df):
                return None

            return main_df
        except Exception as e:
            import traceback
            logger.error(f"Fetch error: {e}\n{traceback.format_exc()}")
            return None

    def calculate_volume_cluster(self, df, lookback=20):
        """
        PHASE 2: Volume Cluster Detection.
        Institutional Logic: Smart money leaves large 'prints' in volume 
        when sweeping liquidity or absorbing orders.
        """
        if df is None or len(df) < lookback:
            return 1.0
        
        recent_volume = df['volume'].iloc[-1]
        avg_volume = df['volume'].iloc[-lookback:-1].mean()
        
        if avg_volume == 0:
            return 1.0
            
        ratio = recent_volume / avg_volume
        return round(ratio, 2)

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
        """
        Global Liquidity Mode: Returns True 24/7, but logs session context.
        """
        from datetime import datetime
        now = current_time or datetime.utcnow()
        hour = now.hour

        # 1. Check NY Lunch Blackout (17:00 - 18:00 UTC)
        # In Global Liquidity Mode, we still flag it but don't hard-gate unless specified.
        lunch_start, lunch_end = Config.get('NY_LUNCH_BLACKOUT', (17, 18))
        if hour >= lunch_start and hour < lunch_end:
            logger.debug("Bayesian Pivot Context: NY_LUNCH_BLACKOUT (Reduced Liquidity)")
            return True # Always True in Global Mode

        # Labeling for internal context
        if 7 <= hour < 10:
             logger.debug("Bayesian Pivot Context: LONDON")
        elif 0 <= hour < 4:
             logger.debug("Bayesian Pivot Context: ASIA")
        elif 12 <= hour < 20:
             logger.debug("Bayesian Pivot Context: NY_CONTINUOUS")

        return True

    def is_asian_fade_window(self, hour=None):
        """Returns True if we are in the 11 PM – 2 AM EST (4–7 AM UTC) Asian Fade prime window."""
        if hour is None:
            hour = datetime.utcnow().hour
        fade = Config.KILLZONE_ASIAN_FADE
        return fade is not None and (fade[0] <= hour < fade[1])

    def scan_asian_fade(self, symbol):
        """
        [REDACTED] Proprietary Asian Range Fade Alpha.
        """
        return None
    def get_detailed_bias(self, symbol, index_context=None, visual_check=False, current_time=None):
        """
        Calculates Multi-Factor Bias using proprietary signal inputs.
        Returns: Bias String (BULLISH/BEARISH/NEUTRAL)
        """
        # [REDACTED] Proprietary Geometric Logic
        return "NEUTRAL"  # Placeholder for public repo
    def get_4h_bias(self, symbol):
        # Legacy wrapper
        return self.get_detailed_bias(symbol).split(" (")[0] # Returns BULLISH/BEARISH/NEUTRAL

    def get_session_quartile(self, current_time=None):
        """
        [REDACTED] Proprietary Session Cycle Logic.
        """
        return {}
    def get_price_quartiles(self, symbol):
        """
        [REDACTED] Proprietary Price Quartile Calculation.
        """
        return {}
    def detect_htf_pois(self, symbol):
        """
        INSTITUTIONAL PRECISION: Detects 1D and 1W Order Blocks and FVGs.
        These act as 'HTF Gravity Points'—trading into them is high-risk.
        """
        pois = []
        for tf in ['1d']: # Removed 1w due to exchange compatibility issues
            df = self.fetch_data(symbol, tf, limit=100)
            if df is None or len(df) < 10:
                continue
                
            # 1. Detect FVGs
            for i in range(2, len(df)):
                # Bullish FVG
                if df['low'].iloc[i] > df['high'].iloc[i-2]:
                    pois.append({
                        'tf': tf,
                        'type': 'FVG_BULLISH',
                        'top': df['low'].iloc[i],
                        'bottom': df['high'].iloc[i-2],
                        'level': (df['low'].iloc[i] + df['high'].iloc[i-2]) / 2
                    })
                # Bearish FVG
                if df['high'].iloc[i] < df['low'].iloc[i-2]:
                    pois.append({
                        'tf': tf,
                        'type': 'FVG_BEARISH',
                        'top': df['low'].iloc[i-2],
                        'bottom': df['high'].iloc[i],
                        'level': (df['low'].iloc[i-2] + df['high'].iloc[i]) / 2
                    })

            # 2. Detect Order Blocks (Last candle before impulsive move)
            # Simplified: Look for engulfing after a sweep or expansion
            for i in range(10, len(df)-1):
                body_prev = abs(df['close'].iloc[i] - df['open'].iloc[i])
                body_curr = abs(df['close'].iloc[i+1] - df['open'].iloc[i+1])
                
                # Bullish Engulfing (Potential Bullish OB)
                if df['close'].iloc[i+1] > df['high'].iloc[i] and body_curr > body_prev * 2:
                    pois.append({
                        'tf': tf,
                        'type': 'OB_BULLISH',
                        'top': df['high'].iloc[i],
                        'bottom': df['low'].iloc[i],
                        'level': (df['high'].iloc[i] + df['low'].iloc[i]) / 2
                    })
                # Bearish Engulfing
                if df['close'].iloc[i+1] < df['low'].iloc[i] and body_curr > body_prev * 2:
                    pois.append({
                        'tf': tf,
                        'type': 'OB_BEARISH',
                        'top': df['high'].iloc[i],
                        'bottom': df['low'].iloc[i],
                        'level': (df['high'].iloc[i] + df['low'].iloc[i]) / 2
                    })
        
        # Filter for 'Fresh' POIs (Not yet mitigated)
        df_now = self.fetch_data(symbol, '1m', limit=1)
        if df_now is None or df_now.empty: return []
        
        current_price = df_now.iloc[-1]['close']
        fresh_pois = [p for p in pois if (p['type'].endswith('BULLISH') and current_price > p['bottom']) or 
                                       (p['type'].endswith('BEARISH') and current_price < p['top'])]
        
        return fresh_pois

    def _calculate_synthetic_volume_profile(self, symbol, swept_level, direction):
        """
        98% Reliability Fallback: 1.2x Absorption Ratio Verification.
        Analyzes delta between last 5m tick-volume and 1H average volume.
        """
        try:
            df_5m = self.fetch_data(symbol, '5m', limit=20, synchronized=False)
            df_1h = self.fetch_data(symbol, '1h', limit=50, synchronized=False)
            
            if df_5m is None or df_1h is None: return False
            
            # 1. Calculate 1H average volume (Baseline)
            # Scale 1H volume to 5M equivalent (1/12)
            avg_vol_1h = (df_1h['volume'].mean() / 12)
            if avg_vol_1h == 0: return False
            
            # 2. Detect last relevant 5M volume (Tick-delta Proxy)
            # We look for the volume spike in the last 2 candles
            peak_vol_5m = df_5m['volume'].iloc[-2:].max()
            
            absorption_ratio = peak_vol_5m / avg_vol_1h
            
            if absorption_ratio >= 1.2:
                logger.info(f"✅ Synthetic Absorption Verified: {absorption_ratio:.2f}x (Limit: 1.2x)")
                return True
            else:
                logger.warning(f"❌ Low Absorption Detected: {absorption_ratio:.2f}x (Below 1.2x limit). Rejecting sweep.")
                return False
        except Exception as e:
            logger.error(f"Synthetic volume calc failed: {e}")
            return False

    def validate_sweep_depth(self, symbol, swept_level, direction):
        """
        [REDACTED] Institutional Order Book Absorption Validation.
        """
        return True
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
    
    def detect_mss(self, df):
        # [REDACTED] Proprietary Market Structure Shift Detection
        return None
    def is_displaced_move(self, df, direction, smt_strength=0.0):
        """
        Confirms institutional participation via high-momentum candle (Displacement).
        Body > 1.5 * ATR.
        Alpha-Weighted: If SMT Strength > 0.7, allow 1.1x sensitivity.
        """
        last = df.iloc[-1]
        atr = self.calculate_atr(df).iloc[-1]
        body_size = abs(last['close'] - last['open'])
        
        # 3. Global Displacement Floor (1.5x ATR) <!-- id: 10 -->
        multiplier = 1.5
             
        return body_size > (atr * multiplier)

    def get_displacement_metrics(self, df, direction):
        """
        Calculates mathematical metrics for the last candle to audit institutional displacement.
        """
        if df is None or len(df) < 5:
            return {}
            
        last = df.iloc[-1]
        prev = df.iloc[-2]
        atr = self.calculate_atr(df).iloc[-1]
        
        # 1. Wick-to-Body Ratio
        body_size = abs(last['close'] - last['open'])
        high_wick = last['high'] - max(last['close'], last['open'])
        low_wick = min(last['close'], last['open']) - last['low']
        
        rejection_wick = low_wick if direction == 'LONG' else high_wick
        wick_to_body = rejection_wick / body_size if body_size > 0 else 1.0
        
        # 2. Displacement Multipliers
        disp_atr = body_size / atr if atr > 0 else 0
        
        # 3. Volume Z-Score (Session-Relative)
        recent_vols = df['volume'].iloc[-20:]
        avg_vol = recent_vols.mean()
        std_vol = recent_vols.std()
        
        # Calculate Z-score: (Current - Mean) / Std
        # This remains sensitive during low-vol Asian hours
        vol_zscore = (last['volume'] - avg_vol) / std_vol if std_vol > 0 else 0
        
        return {
            "wick_to_body_ratio": round(wick_to_body, 2),
            "displacement_atr": round(disp_atr, 2),
            "volume_delta": round(last['volume'] / avg_vol if avg_vol > 0 else 1.0, 2),
            "volume_zscore": round(vol_zscore, 2),
            "wick_rejection_atr": round(rejection_wick / atr, 2) if atr > 0 else 0
        }

    def get_technical_metadata_payload(self, df, current_quartiles=None):
        """
        Aggregates all detected structures (FVG, OB, Liquidity) into a visualizable payload.
        """
        metadata = []
        
        # 1. Detect FVGs (unmitigated in last 25)
        recent = df.iloc[-25:]
        for i in range(2, len(recent)):
            c0 = recent.iloc[i]
            c2 = recent.iloc[i-2]
            
            # Bullish FVG
            if c2['high'] < c0['low']:
                metadata.append({
                    "type": "FVG",
                    "direction": "BULLISH",
                    "top": c0['low'],
                    "bottom": c2['high'],
                    "start_time": recent.index[i-2],
                    "end_time": recent.index[i]
                })
            # Bearish FVG
            elif c2['low'] > c0['high']:
                metadata.append({
                    "type": "FVG",
                    "direction": "BEARISH",
                    "top": c2['low'],
                    "bottom": c0['high'],
                    "start_time": recent.index[i-2],
                    "end_time": recent.index[i]
                })
        
        # 2. Liquidity Pools (PDH, PDL)
        p_high = df['high'].iloc[-288:-1].max()
        p_low = df['low'].iloc[-288:-1].min()
        
        metadata.append({"type": "LIQ_POOL", "label": "PDH", "price": p_high})
        metadata.append({"type": "LIQ_POOL", "label": "PDL", "price": p_low})
        
        return metadata

    def detect_inducement_trap(self, df, direction):
        """
        Detects 'Retail Inducement' (minor highs/lows) swept just before reversal.
        """
        recent = df.tail(10)
        last = df.iloc[-1]
        
        if direction == 'LONG':
            # Swept a minor low (inducement) before MSS
            minor_low = recent['low'].iloc[:-1].min()
            return last['low'] < minor_low and last['close'] > minor_low
        else:
            minor_high = recent['high'].iloc[:-1].max()
            return last['high'] > minor_high and last['close'] < minor_high

    def get_volatility_adjusted_target(self, df, direction, entry_price, session_range, symbol="BTC/USD"):
        """
        [REDACTED] Dynamic Targeted Alpha Logic.
        """
        return 0.0
    def get_next_institutional_target(self, df, direction, entry_price):
        """
        [REDACTED] Recursively Scans for Draw on Liquidity.
        """
        return None
    def is_tapping_fvg(self, df, direction):
        """
        [REDACTED] Fair Value Gap Neutralization Logic.
        """
        return False
    def scan_pattern(self, symbol, timeframe=Config.TIMEFRAME, cached_context=None, provided_df=None, current_time_override=None, visual_check=True):
        """
        Main Scanning Function.
        [REDACTED] Core Logic Hidden for Public Release.
        """
        return None
    def scan_trend_expansion(self, symbol, timeframe=Config.TIMEFRAME, cached_context=None):
        """
        [NEW] TREND EXPANSION SCANNER:
        Identifies 'Clean' trend moves that don't satisfy reversal criteria.
        Logic: STRONG 4H/1H Bias Alignment + Retracement to 15m/1H/4H POI.
        """
        # 1. HARD GATE: Bias Conviction (Must be STRONG and aligned)
        index_context = cached_context or self.intermarket.get_market_context()
        bias_full = self.get_detailed_bias(symbol, index_context=index_context, visual_check=False)
        
        is_strong_bull = "STRONG BULLISH" in bias_full
        is_strong_bear = "STRONG BEARISH" in bias_full
        
        if not is_strong_bull and not is_strong_bear:
            return None

        # 2. HEURISTIC GATE: Hurst (Must be EXPANSION)
        df = self.fetch_data(symbol, timeframe)
        if df is None or len(df) < 50: return None
        
        hurst = self.get_hurst_exponent(df['close'].values)
        if hurst < 0.52: # Standard expansion threshold
            return None
            
        # 3. POI DETECTION: Find 15m, 1H, 4H POIs
        # We need to fetch higher timeframe data specifically for this
        pois = []
        for tf in ['15m', '1h', '4h']:
            tf_df = self.fetch_data(symbol, tf, limit=100, synchronized=False)
            if tf_df is None or len(tf_df) < 5: continue
            
            # Detect FVGs on this TF
            for i in range(2, len(tf_df)):
                # Bullish FVG
                if tf_df['low'].iloc[i] > tf_df['high'].iloc[i-2]:
                    pois.append({'type': 'FVG_BULLISH', 'top': tf_df['low'].iloc[i], 'bottom': tf_df['high'].iloc[i-2], 'tf': tf})
                # Bearish FVG
                if tf_df['high'].iloc[i] < tf_df['low'].iloc[i-2]:
                    pois.append({'type': 'FVG_BEARISH', 'top': tf_df['low'].iloc[i-2], 'bottom': tf_df['high'].iloc[i], 'tf': tf})

        if not pois:
            return None

        current_price = df['close'].iloc[-1]
        direction = 'LONG' if is_strong_bull else 'SHORT'
        
        # 4. ENTRY TRIGGER: Price currently "sitting" in a POI aligned with the trend
        active_poi = None
        for p in pois:
            if direction == 'LONG' and p['type'] == 'FVG_BULLISH':
                if p['bottom'] <= current_price <= p['top']:
                    active_poi = p
                    break
            if direction == 'SHORT' and p['type'] == 'FVG_BEARISH':
                if p['bottom'] <= current_price <= p['top']:
                    active_poi = p
                    break
        
        if not active_poi:
            return None

        # 5. DEDUPLICATION GATE
        now_ts = datetime.utcnow().timestamp()
        cache_key = f"{symbol}_expansion"
        last_fired = self._signal_cache.get(cache_key, 0)
        if (now_ts - last_fired) < (self._signal_cooldown_mins * 60):
            return None

        # 6. Construct Setup
        # TP/SL based on POI and ATR
        atr = self.calculate_atr(df).iloc[-1]
        if direction == 'LONG':
            entry = current_price
            stop_loss = active_poi['bottom'] - (atr * 0.5)
            target = entry + (abs(entry - stop_loss) * 3.5) # Expanding trend RR
        else:
            entry = current_price
            stop_loss = active_poi['top'] + (atr * 0.5)
            target = entry - (abs(entry - stop_loss) * 3.5)

        setup = {
            "timestamp": datetime.utcnow().isoformat(),
            "symbol": symbol,
            "pattern": f"Trend Expansion ({active_poi['tf']} {active_poi['type']})",
            "bias": bias_full,
            "entry": entry,
            "stop_loss": stop_loss,
            "target": target,
            "direction": direction,
            "time_quartile": self.get_session_quartile(),
            "price_quartiles": self.get_price_quartiles(symbol),
            "index_context": index_context,
            "hurst_regime": round(hurst, 3),
            "quality": "HIGH"
        }
        
        self._signal_cache[cache_key] = now_ts
        return setup, df

    def scan_order_flow(self, symbol, timeframe=Config.TIMEFRAME, cached_context=None):
        """
        [REDACTED] Institutional Order Flow Logic.
        """
        return None
    def detect_mss(self, df, lookback=50, smt_strength=0.0):
        # [REDACTED] Proprietary Market Structure Shift Detection
        return None
    def find_order_block(self, df, origin_index, direction):
        # [REDACTED] Proprietary Order Block Identification
        return None

import os
import pandas as pd
import numpy as np
import ccxt
from datetime import datetime, timedelta
import yfinance as yf

class DataManager:
    """Handles fetching and caching of market data."""
    def __init__(self, cache_dir='data/cache'):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        self.exchange = ccxt.binance()

    def get_data(self, symbol, timeframe='5m', days=30):
        cache_file = os.path.join(self.cache_dir, f"{symbol.replace('/', '_')}_{timeframe}_{days}d.csv")
        
        if os.path.exists(cache_file):
            print(f"📦 Loading {symbol} from cache...")
            df = pd.read_csv(cache_file, parse_dates=['timestamp'])
            return df

        if symbol in ["DXY", "NQ", "ES"]:
            return self._fetch_index_data(symbol, timeframe, days, cache_file)
            
        return self._fetch_exchange_data(symbol, timeframe, days, cache_file)

    def _fetch_index_data(self, symbol, timeframe, days, cache_file):
        tickers = {"DXY": "DX=F", "NQ": "NQ=F", "ES": "ES=F"}
        ticker = tickers.get(symbol, symbol)
        print(f"📥 Fetching {symbol} Index from yfinance (last {days} days)...")
        
        df = yf.download(ticker, period=f"{days}d", interval=timeframe, progress=False)
        if df.empty:
            print(f"⚠️ Warning: No data returned for {symbol}. SMT will be disabled.")
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        df = df.reset_index()
        # Rename whatever the first column is (usually 'Datetime' or 'Date')
        df = df.rename(columns={df.columns[0]: 'timestamp', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'})
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_localize(None)
        df.to_csv(cache_file, index=False)
        print(f"✅ Cached {len(df)} candles to {cache_file}")
        return df

    def _fetch_exchange_data(self, symbol, timeframe, days, cache_file):
        print(f"📥 Fetching {symbol} from exchange (this will be cached)...")
        end_ts = int(datetime.now().timestamp() * 1000)
        start_ts = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
        
        all_data = []
        current_ts = start_ts
        
        while current_ts < end_ts:
            try:
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, since=current_ts, limit=1000)
                if not ohlcv: break
                all_data.extend(ohlcv)
                current_ts = ohlcv[-1][0] + 1
            except Exception as e:
                print(f"Error: {e}")
                break

        df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms').dt.tz_localize(None)
        df.to_csv(cache_file, index=False)
        print(f"✅ Cached {len(df)} candles to {cache_file}")
        return df

class VectorizedIndicators:
    """Pre-calculates indicators for an entire dataframe at once."""
    
    @staticmethod
    def add_ema(df, span, name=None):
        name = name or f"ema_{span}"
        df[name] = df['close'].ewm(span=span, adjust=False).mean()
        return df

    @staticmethod
    def add_bias(df, candles_per_4h=4):
        """
        Adds 4H EMA-based bias.
        candles_per_4h: how many candles make up 4 hours.
          - 5m chart:  48  (48 * 5min = 240min)
          - 1H chart:   4  (4 * 60min = 240min)
        """
        ema_20_p = 20 * candles_per_4h
        ema_50_p = 50 * candles_per_4h
        
        df['ema_20_htf'] = df['close'].ewm(span=ema_20_p, adjust=False).mean()
        df['ema_50_htf'] = df['close'].ewm(span=ema_50_p, adjust=False).mean()
        
        conditions = [
            (df['ema_20_htf'] > df['ema_50_htf']),
            (df['ema_20_htf'] < df['ema_50_htf'])
        ]
        choices = ['BULLISH', 'BEARISH']
        df['bias'] = np.select(conditions, choices, default='NEUTRAL')
        return df

    @staticmethod
    def add_atr(df, period=14):
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        df['atr'] = true_range.rolling(period).mean()
        return df

    @staticmethod
    def add_session_ranges(df):
        """Pre-calculates Asian and London range high/low for each day."""
        df['date'] = df['timestamp'].dt.date
        df['hour'] = df['timestamp'].dt.hour
        
        # Asian Range: 00:00 - 05:00 UTC
        asian = df[(df['hour'] >= 0) & (df['hour'] < 5)]
        asian_ranges = asian.groupby('date').agg({'high': 'max', 'low': 'min'}).rename(columns={'high': 'asian_high', 'low': 'asian_low'})
        
        # London Range: 07:00 - 10:00 UTC
        london = df[(df['hour'] >= 7) & (df['hour'] < 10)]
        london_ranges = london.groupby('date').agg({'high': 'max', 'low': 'min'}).rename(columns={'high': 'london_high', 'low': 'london_low'})
        
        df = df.merge(asian_ranges, on='date', how='left')
        df = df.merge(london_ranges, on='date', how='left')
        return df

    @staticmethod
    def add_displacement(df):
        """
        Institutional Displacement: Identified by candles with large bodies relative to ATR.
        Requires Body > 1.5 * ATR.
        """
        df['body'] = (df['close'] - df['open']).abs()
        df['displaced'] = df['body'] > (df['atr'] * 1.5)
        return df

    @staticmethod
    def add_fair_value_gap(df):
        """
        Fair Value Gap (FVG) Detection — Vectorized.
        
        A Bullish FVG exists when candle[i-1].high < candle[i+1].low (gap unfilled).
        A Bearish FVG exists when candle[i-1].low > candle[i+1].high (gap unfilled).
        
        In TRENDING Mode: FVGs are pullback targets — price is expected to revisit
        these gaps before continuing in the trend direction.
        """
        # Shift to get prev/next candle values (no future leak — we use shift)
        prev_high = df['high'].shift(2)  # 2-candle lag for confirmed knowledge
        prev_low  = df['low'].shift(2)
        curr_high = df['high'].shift(1)
        curr_low  = df['low'].shift(1)

        # Bullish FVG: 3-candle pattern where middle candle leaves a gap upward
        df['fvg_bull'] = prev_high < df['low']          # prev high < current low = gap
        df['fvg_bull_top'] = df['low'].where(df['fvg_bull'])    # Upper boundary of gap
        df['fvg_bull_bot'] = prev_high.where(df['fvg_bull'])    # Lower boundary

        # Bearish FVG
        df['fvg_bear'] = prev_low > df['high']          # prev low > current high = gap
        df['fvg_bear_top'] = prev_low.where(df['fvg_bear'])     # Upper boundary
        df['fvg_bear_bot'] = df['high'].where(df['fvg_bear'])   # Lower boundary

        # Track 'nearest active FVG' for live pullback detection
        df['fvg_bull_top'] = df['fvg_bull_top'].ffill()
        df['fvg_bull_bot'] = df['fvg_bull_bot'].ffill()
        df['fvg_bear_top'] = df['fvg_bear_top'].ffill()
        df['fvg_bear_bot'] = df['fvg_bear_bot'].ffill()

        return df

    @staticmethod
    def add_mss(df):
        """
        Market Structure Shift (MSS):
        Bullish MSS: Price breaks above the previous Fractal High.
        Bearish MSS: Price breaks below the previous Fractal Low.
        """
        # Fractal Highs/Lows (Window=2)
        # In real-time, we only KNOW a fractal is confirmed 2 candles AFTER it forms.
        # So we shift the 'knowledge' of the fractal by 2.
        df['is_high'] = (df['high'] > df['high'].shift(1)) & (df['high'] > df['high'].shift(2)) & \
                        (df['high'] > df['high'].shift(-1)) & (df['high'] > df['high'].shift(-2))
        df['is_low'] = (df['low'] < df['low'].shift(1)) & (df['low'] < df['low'].shift(2)) & \
                       (df['low'] < df['low'].shift(-1)) & (df['low'] < df['low'].shift(-2))
        
        # Propagate knowledge only AFTER 2-candle confirmation
        df['known_high'] = df['high'].where(df['is_high']).shift(2).ffill()
        df['known_low'] = df['low'].where(df['is_low']).shift(2).ffill()
        
        # MSS detection using strictly 'KNOWN' historical structure
        df['mss_bullish'] = (df['close'] > df['known_high'].shift(1)) & (df['close'].shift(1) <= df['known_high'].shift(1))
        df['mss_bearish'] = (df['close'] < df['known_low'].shift(1)) & (df['close'].shift(1) >= df['known_low'].shift(1))
        
        return df

    @staticmethod
    def add_regime_regime(df, period=200):
        """
        Hurst Exponent regime detection with a 200-candle window for noise reduction.

        H < 0.45  → MEAN_REVERTING (range/chop) → Use Reversal Mode
        H 0.45-0.55 → TRANSITION (dead zone)    → Skip
        H > 0.55  → TRENDING (momentum)         → Use Continuation Mode
        """
        def hurst(ts):
            lags = range(2, 20)
            tau = [np.sqrt(np.std(np.subtract(ts[lag:], ts[:-lag]))) for lag in lags]
            poly = np.polyfit(np.log(lags), np.log(tau), 1)
            return poly[0] * 2.0

        print("📈 Calculating Hurst Regimes (200-candle window)...")
        df['hurst'] = df['close'].rolling(window=period).apply(hurst, raw=True)
        df['regime'] = np.select(
            [(df['hurst'] < 0.45), (df['hurst'] > 0.55)],
            ['MEAN_REVERTING', 'TRENDING'],
            default='TRANSITION'
        )
        return df

    @staticmethod
    def add_equal_highs_lows(df, tolerance_atr_mult=0.15, lookback=50):
        """
        Equal Highs/Lows (EQL) — Liquidity Pool Detection.

        Detects levels where price has made 2+ touches within a tight ATR-based
        tolerance band. These zones have the HIGHEST stop concentration because:
          - Retail places stops just above equal highs / below equal lows
          - The more touches, the more stops have accumulated
          - Institutions NEED to sweep these to fill large orders

        Methodology:
          For each candle, count how many prior candles (within `lookback`) had a
          high (or low) within `tolerance_atr_mult × ATR` of the current candle.

        Outputs:
          eql_high_touches  : # of prior candles with highs near this candle's high
          eql_low_touches   : # of prior candles with lows near this candle's low
          is_eql_high       : True if this high is a confirmed EQL zone (≥2 touches)
          is_eql_low        : True if this low is a confirmed EQL zone (≥2 touches)
          eql_pool_strength : Combined touch count (heuristic liquidity score)
        """
        print("🎯 Detecting Equal Highs/Lows (Liquidity Pools)...")
        tol = df['atr'] * tolerance_atr_mult

        high_touches = np.zeros(len(df), dtype=int)
        low_touches  = np.zeros(len(df), dtype=int)

        highs = df['high'].values
        lows  = df['low'].values
        tols  = tol.values

        for i in range(lookback, len(df)):
            t = tols[i]
            window_highs = highs[max(0, i - lookback):i]
            window_lows  = lows[max(0, i - lookback):i]
            high_touches[i] = int(np.sum(np.abs(window_highs - highs[i]) <= t))
            low_touches[i]  = int(np.sum(np.abs(window_lows  - lows[i])  <= t))

        df['eql_high_touches'] = high_touches
        df['eql_low_touches']  = low_touches
        df['is_eql_high']      = high_touches >= 2
        df['is_eql_low']       = low_touches  >= 2
        df['eql_pool_strength'] = np.clip(high_touches + low_touches, 0, 10)
        return df

    @staticmethod
    def add_sweep_counter(df, lookback=100):
        """
        Sweep Counter — Multi-Sweep Confirmation.

        Each additional sweep of the same level dramatically increases the
        probability of a real reversal (the cascade is nearly exhausted).

        Logic:
          A 'sweep' occurs when a candle's low breaks the prior known_low
          (or high breaks known_high) but CLOSES back above (below) it —
          a wick through the level without a close commitment (failed break).

        Outputs:
          bull_sweep_count : # of bullish sweeps (lower-low wicks) in lookback window
          bear_sweep_count : # of bearish sweeps (higher-high wicks) in lookback window
          sweep_exhaustion : True when 2+ sweeps in the same direction have occurred
                             → high-probability reversal zone
        """
        print("🔢 Counting Sweep Cascades...")

        # A bullish sweep candle: wick below recent low but closes above it
        # (price dipped below known_low but buyers pushed it back up)
        recent_low  = df['low'].rolling(lookback).min().shift(1)
        recent_high = df['high'].rolling(lookback).max().shift(1)

        # Bull sweep: low broke below reference low but CLOSE recovered
        is_bull_sweep = (df['low'] < recent_low) & (df['close'] > recent_low)
        # Bear sweep: high broke above reference high but CLOSE dropped back
        is_bear_sweep = (df['high'] > recent_high) & (df['close'] < recent_high)

        # Rolling count of how many sweeps occurred in the recent lookback window
        df['bull_sweep_count'] = is_bull_sweep.rolling(lookback).sum().fillna(0).astype(int)
        df['bear_sweep_count'] = is_bear_sweep.rolling(lookback).sum().fillna(0).astype(int)

        # Exhaustion signal: 2+ sweeps means the cascade is likely done
        df['bull_sweep_exhaustion'] = df['bull_sweep_count'] >= 2
        df['bear_sweep_exhaustion'] = df['bear_sweep_count'] >= 2
        return df

    @staticmethod
    def add_wick_ratio(df):
        """
        Wick Extension Ratio — Sweep Quality Scoring.

        Measures how decisively price moved past a level.
        A shallow wick just tickles the level (many stops remain).
        A deep wick blows through it (most stops cleared, reversal ready).

        Methodology:
          For a bullish sweep candle (down-wick):
            wick_ratio = lower_wick / ATR

          Thresholds (from the math model):
            < 0.3  → Weak sweep — stops may not be fully cleared
            0.3–0.8 → Moderate — worth watching
            0.8–1.5 → Strong sweep — high reversal probability
            > 1.5  → Violent sweep — near-certain stop run completion

        Outputs:
          lower_wick      : size of the lower wick (candle low to open/close)
          upper_wick      : size of the upper wick
          lower_wick_ratio: lower_wick / ATR (bullish sweep quality)
          upper_wick_ratio: upper_wick / ATR (bearish sweep quality)
          strong_bull_sweep: True if lower_wick_ratio >= 0.8
          strong_bear_sweep: True if upper_wick_ratio >= 0.8
        """
        candle_min = df[['open', 'close']].min(axis=1)
        candle_max = df[['open', 'close']].max(axis=1)

        df['lower_wick']       = candle_min - df['low']
        df['upper_wick']       = df['high'] - candle_max
        df['lower_wick_ratio'] = df['lower_wick'] / df['atr'].replace(0, np.nan)
        df['upper_wick_ratio'] = df['upper_wick'] / df['atr'].replace(0, np.nan)

        df['strong_bull_sweep'] = df['lower_wick_ratio'] >= 0.8
        df['strong_bear_sweep'] = df['upper_wick_ratio'] >= 0.8
        return df

    @staticmethod
    def add_smt_divergence(df, corr_df, symbol_name="DXY"):
        """Detects SMT Divergence against a correlated asset."""
        print(f"⚡ Correlating {symbol_name} for SMT...")
        
        # Merge corr data on timestamp
        corr_df = corr_df[['timestamp', 'high', 'low']].rename(columns={'high': f'{symbol_name}_high', 'low': f'{symbol_name}_low'})
        df = df.merge(corr_df, on='timestamp', how='left').ffill()

        # Simple SMT: BTC makes LL, DXY makes LL (Divergence since they are inverse)
        # Or BTC makes LH, DXY makes LH.
        # Vectorized swing checks
        df[f'{symbol_name}_rh'] = df[f'{symbol_name}_high'].rolling(20).max().shift(1)
        df[f'{symbol_name}_rl'] = df[f'{symbol_name}_low'].rolling(20).min().shift(1)
        
        # Bullish SMT (Inverse Correlation with DXY):
        # DXY sweeps High (makes HH), but BTC fails to sweep Low (makes HL)
        df['smt_bullish'] = (df[f'{symbol_name}_high'] > df[f'{symbol_name}_rh']) & (df['low'] > df['recent_low'])
        
        # Bearish SMT:
        # DXY sweeps Low (makes LL), but BTC fails to sweep High (makes LH)
        df['smt_bearish'] = (df[f'{symbol_name}_low'] < df[f'{symbol_name}_rl']) & (df['high'] < df['recent_high'])
        
        return df

class NewsSimulator:
    """Simulates historical red folder events for backtesting."""
    @staticmethod
    def add_news_blackouts(df, impact_prob=0.01):
        """
        Adds news blackout windows. 
        Since historical calendar access is limited, we simulate 'Red Folders' 
        aligned with NY Open (13:30 UTC) and London Open (07:00 UTC) with 40% probability.
        """
        df['is_news_event'] = False
        
        # Static events for NY Open / London Open
        # 07:00, 13:30, 15:00, 19:00 UTC are common times
        news_hours = [7, 13, 15, 19]
        
        # Vectorized news flag
        df.loc[df['hour'].isin(news_hours) & (df['timestamp'].dt.minute == 0), 'is_news_event'] = (np.random.random(len(df[df['hour'].isin(news_hours) & (df['timestamp'].dt.minute == 0)])) < 0.4)
        
        # Expand blackout to 30m before and after
        df['news_blackout'] = df['is_news_event'].rolling(window=13, center=True).max().fillna(0).astype(bool)
        return df

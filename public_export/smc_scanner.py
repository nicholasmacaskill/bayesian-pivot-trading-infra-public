# [PUBLIC PORTFOLIO VERSION]
# NOTE: Core proprietary logic and parameters have been redacted/standardized.
# This repository demonstrates architecture, not live trading alpha.

import numpy as np
import pandas as pd
from smartmoneyconcepts import smc  # Assuming leveraging the library for core calculations, or custom implementing
import ccxt
import time
from datetime import datetime, time as time_obj
from config import Config
from intermarket_engine import IntermarketEngine
from news_filter import NewsFilter
import logging

logger = logging.getLogger(__name__)

class SMCScanner:
    def __init__(self):
        # Initialize public exchange for data fetching (free tier)
        self.exchange = ccxt.binance({'enableRateLimit': True})
        self.intermarket = IntermarketEngine()
        self.news = NewsFilter()
        self.order_book_enabled = True  # Can be disabled if exchange doesn't support
        
    def calculate_atr(self, df, period=14):
        high_low = df['high'] - df['low']
        high_close = abs(df['high'] - df['close'].shift())
        low_close = abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        return true_range.rolling(period).mean()

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
            # Map symbol to yfinance format (BTC/USDT -> BTC-USD)
            yf_symbol = symbol.replace('/', '-') if '/' in symbol else symbol
            if yf_symbol == 'BTC-USDT': yf_symbol = 'BTC-USD'
            
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
            
            return df

        except Exception as e:
            logger.error(f"Error fetching data via yfinance for {symbol}: {e}")
            return None

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

    def is_killzone(self):
        """Checks if current time is within London or NY session"""
        now_utc = datetime.utcnow().time()
        hour = now_utc.hour
        
        # Check London Session
        london = Config.KILLZONE_LONDON
        if london and (london[0] <= hour < london[1]):
            return True

        # Check continuous NY session
        ny_session = Config.KILLZONE_NY_CONTINUOUS
        if ny_session and (ny_session[0] <= hour < ny_session[1]):
            return True
        
        return False

    def get_4h_bias(self, symbol):
        """Determines HTF Trend Bias from 4H chart"""
        df_4h = self.fetch_data(symbol, Config.HTF_TIMEFRAME, limit=100)
        if df_4h is None:
            return "NEUTRAL"
            
        # Simple EMA Strategy for Bias (20 vs 50)
        df_4h['ema_20'] = df_4h['close'].ewm(span=20).mean()
        df_4h['ema_50'] = df_4h['close'].ewm(span=50).mean()
        
        latest = df_4h.iloc[-1]
        if latest['ema_20'] > latest['ema_50']:
            return "BULLISH"
        elif latest['ema_20'] < latest['ema_50']:
            return "BEARISH"
        return "NEUTRAL"

    def get_session_quartile(self):
        """
        Calculates the current ICT Session Quartile (90-minute cycles).
        Identifies the phase: Accumulation, Manipulation, Distribution, or X.
        """
        now_utc = datetime.utcnow()
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

    def get_price_quartiles(self, symbol):
        """
        Calculates Asian Range and CBDR High/Low and their Quartiles (SDs).
        Asian Range: 00:00 - 05:00 UTC
        CBDR: 19:00 - 01:00 UTC
        """
        # Fetch 24h of data to find ranges
        df_range = self.fetch_data(symbol, '15m', limit=100)
        if df_range is None: return None
        
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
                return total_volume >= 1.0 # [VOLUME THRESHOLD REDACTED]
            
            # For SHORT setup (sweep above), check sell-side absorption
            else:
                asks = order_book['asks']
                total_volume = 0
                
                for ask in asks:
                    price, amount = ask[0], ask[1]
                    if abs(price - swept_level) / swept_level < 0.005:
                        total_volume += amount
                
                return total_volume >= 1.0 # [VOLUME THRESHOLD REDACTED]
        
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
        Low Volatility (ATR < mean): Target nearest FVG or 50% mean (take quick profit)
        Normal Volatility: Target SD 1.0 (current strategy)
        
        Args:
            df: OHLCV dataframe
            direction: 'LONG' or 'SHORT'
            entry_price: Entry price
            session_range: Price quartiles dict
        
        Returns:
            Target price
        """
        atr = self.calculate_atr(df)
        if atr is None or len(atr) < 14:
            # Fallback to SD 1.0 if ATR unavailable
            return session_range.get('sd_1_pos' if direction == 'LONG' else 'sd_1_neg')
        
        mean_atr = atr.iloc[-50:].mean()  # 50-period mean
        current_atr = atr.iloc[-1]
        
        # High Volatility: Expanded Targets
        if current_atr > mean_atr * 1.5:
            logger.info(f"📈 High Volatility Detected (ATR: {current_atr:.2f} > {mean_atr*1.5:.2f}). Targeting SD 2.0")
            return session_range.get('sd_2_pos' if direction == 'LONG' else 'sd_2_neg', 
                                    session_range.get('sd_1_pos' if direction == 'LONG' else 'sd_1_neg'))
        
        # Low Volatility: Tighter Targets
        elif current_atr < mean_atr:
            logger.info(f"📉 Low Volatility Detected (ATR: {current_atr:.2f} < {mean_atr:.2f}). Targeting 50% Mean")
            # Target 50% of range (mean threshold)
            return session_range.get('mid')
        
        # Normal Volatility: SD 1.0 (current strategy)
        else:
            return session_range.get('sd_1_pos' if direction == 'LONG' else 'sd_1_neg')
            
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

    def scan_pattern(self, symbol, timeframe='5m', cached_context=None):
        """
        Main Scanning Function.
        Checks: Killzone -> Trend Bias -> Price Quartiles -> SMC Pattern
        
        Args:
            cached_context: Pre-warmed context from background pulse (optional)
        """
        # 1. HARD GATE: Time (Killzone)
        if not self.is_killzone():
            return None 

        # 2. SOFT GATE: News Context (Use Cache or Live)
        if cached_context and 'news' in cached_context:
            news_data = cached_context['news']
            is_safe = news_data['is_safe']
            event = news_data['event']
            mins = news_data['minutes_until']
        else:
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
            
        # 4. HARD GATE: Bias (HTF 4H)
        bias = self.get_4h_bias(symbol)
        
        # 3. GET SESSION METADATA (Time & Price Quartiles)
        time_quartile = self.get_session_quartile()
        price_quartiles = self.get_price_quartiles(symbol)
        
        df = self.fetch_data(symbol, timeframe)
        if df is None:
            return None

        # Current and recent data
        current = df.iloc[-1]
        
        # Recent high/low for liquidity levels (24h Lookback - PDH/PDL)
        # 288 candles * 5m = 1440m = 24 hours
        recent_high = df['high'].iloc[-288:-1].max()
        recent_low = df['low'].iloc[-288:-1].min()

        setup = None

        # BULLISH Setup: Manipulation (Sweep) below Recent Low
        if bias == "BULLISH":
            # TIER 1 FILTER: Deep Discount Price Quartile (0.00-0.25)
            in_deep_discount = False
            if price_quartiles:
                ref_range = price_quartiles.get("Asian Range") or price_quartiles.get("CBDR")
                if ref_range:
                    price_position = (current['close'] - ref_range['low']) / (ref_range['high'] - ref_range['low'])
                    # Must be in 0.00-0.25 range (Deep Discount)
                    if Config.MIN_PRICE_QUARTILE <= price_position <= Config.MAX_PRICE_QUARTILE:
                        in_deep_discount = True
            
            # TIER 1 FILTER: Strong SMT Divergence (DXY Correlation)
            smt_strength = 0.0
            if index_context:
                # Use DXY (Dollar Index) as the Institutional Truth
                dxy_data = index_context.get('DXY', {})
                if dxy_data:
                    dxy_change = dxy_data.get('change_5m', 0)
                    # Institutional Sponsorship: BTC refuses to drop when DXY pumps.
                    # Or DXY dumps and BTC pumps (Confluence).
                    # We measure the MAGNITUDE of the DXY move.
                    smt_strength = abs(dxy_change) / 0.1  # Normalize: 0.1% move = 1.0 Strength
            
            has_strong_smt = smt_strength >= Config.MIN_SMT_STRENGTH
            
            # HYBRID SWEEP: Check 24h Low (PDL) OR London Low (Session Inducement)
            # Must sweep BELOW the low, but Close ABOVE it (Judas Swing)
            swept_pdl = current['low'] < recent_low and current['close'] > recent_low
            
            swept_london = False
            if price_quartiles and "London Range" in price_quartiles:
                london_low = price_quartiles["London Range"]["low"]
                swept_london = current['low'] < london_low and current['close'] > london_low

            if in_deep_discount and has_strong_smt: # [ENTRY LOGIC REDACTED FOR PUBLIC RELEASE]
                # LEVEL 2 DEPTH FILTER: Validate sweep had institutional absorption
                swept_level = recent_low if swept_pdl else (price_quartiles["London Range"]["low"] if swept_london else recent_low)
                has_depth = self.validate_sweep_depth(symbol, swept_level, 'LONG')
                
                if not has_depth:
                    logger.info(f"❌ Rejected: Sweep lacks depth (Retail Dust). Swept level: ${swept_level:,.2f}")
                    return None
                
                # ATR-DYNAMIC TARGETING: Adjust for volatility
                london_range = price_quartiles.get("London Range") or price_quartiles.get("Asian Range")
                target = self.get_volatility_adjusted_target(df, 'LONG', current['close'], london_range)
                
                if not target:
                    target = self.get_next_institutional_target(df, "LONG", current['close'])

                # STRATEGY: WIDE NET (ATR-Based Stops & Split Targets)
                # Calculate ATR for dynamic stop loss
                atr = self.calculate_atr(df).iloc[-1]
                if pd.isna(atr):
                    atr = current['close'] * 0.005 # Fallback
                
                stop_buffer = atr * Config.STOP_LOSS_ATR_MULTIPLIER
                
                direction = 'LONG'
                stop_loss = current['close'] - stop_buffer
                risk = current['close'] - stop_loss
                target = current['close'] + (risk * Config.TP2_R_MULTIPLE) # We target TP2 for the main signal

                # TRINITY OF SPONSORSHIP: Cross-Asset Divergence
                cross_asset_div = self.intermarket.calculate_cross_asset_divergence('LONG', index_context)

                setup = {
                    "timestamp": current['timestamp'].isoformat() if hasattr(current['timestamp'], 'isoformat') else str(current['timestamp']),
                    "symbol": symbol,
                    "pattern": "Bullish PO3 (Judas Swing)",
                    "bias": bias,
                    "entry": current['close'],
                    "stop_loss": stop_loss,
                    "target": target, # Original target logic
                    'tp1': current['close'] + (risk * Config.TP1_R_MULTIPLE),
                    'direction': direction,
                    "time_quartile": time_quartile,
                    "price_quartiles": price_quartiles,
                    "index_context": index_context,
                    "smt_strength": round(smt_strength, 2),
                    "cross_asset_divergence": round(cross_asset_div, 2),
                    "news_context": news_context,
                    "is_discount": True,
                    'risk_reward': Config.TP2_R_MULTIPLE # Fixed at 3R for Runner
                }

        # BEARISH Setup: Manipulation (Sweep) above Recent High
        elif bias == "BEARISH":
            # TIER 1 FILTER: Premium Price Quartile (0.65-1.00)
            in_premium = False
            if price_quartiles:
                ref_range = price_quartiles.get("Asian Range") or price_quartiles.get("CBDR")
                if ref_range:
                    price_position = (current['close'] - ref_range['low']) / (ref_range['high'] - ref_range['low'])
                    # Must be in premium range
                    if Config.MIN_PRICE_QUARTILE_SHORT <= price_position <= Config.MAX_PRICE_QUARTILE_SHORT:
                        in_premium = True
            
            # TIER 1 FILTER: Strong SMT Divergence (DXY Correlation)
            smt_strength = 0.0
            if index_context:
                dxy_data = index_context.get('DXY', {})
                if dxy_data:
                    dxy_change = dxy_data.get('change_5m', 0)
                    smt_strength = abs(dxy_change) / 0.1
            
            has_strong_smt = smt_strength >= Config.MIN_SMT_STRENGTH
            
            # HYBRID SWEEP: Check 24h High (PDH) OR London High (Session Inducement)
            # Must sweep ABOVE the high, but Close BELOW it (Judas Swing)
            swept_pdh = current['high'] > recent_high and current['close'] < recent_high
            
            swept_london = False
            if price_quartiles and "London Range" in price_quartiles:
                london_high = price_quartiles["London Range"]["high"]
                swept_london = current['high'] > london_high and current['close'] < london_high

            if in_premium and has_strong_smt and (swept_pdh or swept_london):
                # LEVEL 2 DEPTH FILTER: Validate sweep had institutional absorption
                swept_level = recent_high if swept_pdh else (price_quartiles["London Range"]["high"] if swept_london else recent_high)
                has_depth = self.validate_sweep_depth(symbol, swept_level, 'SHORT')
                
                if not has_depth:
                    logger.info(f"❌ Rejected: Sweep lacks depth (Retail Dust). Swept level: ${swept_level:,.2f}")
                    return None
                
                # ATR-DYNAMIC TARGETING: Adjust for volatility
                london_range = price_quartiles.get("London Range") or price_quartiles.get("Asian Range")
                target = self.get_volatility_adjusted_target(df, 'SHORT', current['close'], london_range)
                
                if not target:
                    target = self.get_next_institutional_target(df, "SHORT", current['close'])
                
                # STRATEGY: WIDE NET (ATR-Based Stops & Split Targets)
                atr = self.calculate_atr(df).iloc[-1]
                if pd.isna(atr):
                    atr = current['close'] * 0.005
                
                stop_buffer = atr * Config.STOP_LOSS_ATR_MULTIPLIER
                
                direction = 'SHORT'
                stop_loss = current['close'] + stop_buffer
                risk = stop_loss - current['close']
                target = current['close'] - (risk * Config.TP2_R_MULTIPLE)

                # TRINITY OF SPONSORSHIP: Cross-Asset Divergence
                cross_asset_div = self.intermarket.calculate_cross_asset_divergence('SHORT', index_context)
                
                setup = {
                    "symbol": symbol,
                    "pattern": "Bearish PO3 (Judas Swing)",
                    "bias": bias,
                    "entry": current['close'],
                    "stop_loss": stop_loss,
                    "target": target,
                    'tp1': current['close'] - (risk * Config.TP1_R_MULTIPLE),
                    'direction': direction,
                    "time_quartile": time_quartile,
                    "price_quartiles": price_quartiles,
                    "index_context": index_context,
                    "smt_strength": round(smt_strength, 2),
                    "cross_asset_divergence": round(cross_asset_div, 2),
                    "news_context": news_context,
                    "is_premium": True,
                    'risk_reward': Config.TP2_R_MULTIPLE
                }



        if setup:
            return setup, df
        return None

if __name__ == "__main__":
    scanner = SMCScanner()
    print(f"🚀 Scanning {Config.SYMBOLS[0]}...")
    result = scanner.scan_pattern(Config.SYMBOLS[0])
    if result:
        print(f"✅ Found: {result['pattern']} on {result['symbol']}")
    else:
        print("Thinking... No clean institutional setups found.")

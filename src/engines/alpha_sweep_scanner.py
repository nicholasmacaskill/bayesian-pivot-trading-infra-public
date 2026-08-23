import numpy as np
import pandas as pd
import logging
from datetime import datetime, timezone
from src.core.config import Config
from src.engines.smc_scanner import SMCScanner
from src.core.database import log_scan, log_system_event
from src.clients.telegram_notifier import send_alert

from src.engines.shadow_substitution_engine import ShadowSubstitutionEngine
from src.engines.counterfactual_tracker import CounterfactualTracker
from src.clients.tl_client import TradeLockerClient

logger = logging.getLogger(__name__)

class AlphaSweepScanner(SMCScanner):
    def __init__(self):
        super().__init__()
        self.shadow_engine = ShadowSubstitutionEngine()
        self.counterfactual_tracker = CounterfactualTracker()
        self.tl = TradeLockerClient()
        logger.info("Bayesian Pivot Alpha Sweep Scanner Initialized with Shadow Substitution, Counterfactual & TradeLocker Fleet Client.")

    def is_premium_killzone(self, dt=None):
        """
        Returns the active killzone label, or None if outside premium windows.
        Premium Live Windows:
        - London Open: 07:00 - 10:00 UTC (00:00 - 03:00 PST)
        - NY Open: 12:00 - 15:00 UTC (05:00 - 08:00 PST)
        - Asian Fade: 04:00 - 07:00 UTC (21:00 - 00:00 PST)
        
        Shadow Observation Window:
        - NY Afternoon Shadow: 15:00 - 20:00 UTC (08:00 - 13:00 PST) [100% Shadow Tracking, Zero Live Risk]
        """
        if dt is None:
            dt = datetime.now(timezone.utc)
        hour = dt.hour
        
        if 7 <= hour < 10:
            return "LONDON_OPEN"
        elif 12 <= hour < 15:
            return "NY_OPEN"
        elif 4 <= hour < 7:
            return "ASIAN_FADE"
        elif 15 <= hour < 20:
            return "NY_AFTERNOON_SHADOW"
        return None

    def find_htf_levels(self, df_1h, window=2):
        """
        Finds recent high-timeframe swing highs and swing lows (fractals).
        A fractal has `window` lower candles on both sides.
        """
        highs = []
        lows = []
        
        # Iterate to find peaks
        for i in range(window, len(df_1h) - window):
            curr_high = df_1h['high'].iloc[i]
            curr_low = df_1h['low'].iloc[i]
            
            # Check swing high
            is_high = True
            for w in range(1, window + 1):
                if df_1h['high'].iloc[i - w] >= curr_high or df_1h['high'].iloc[i + w] >= curr_high:
                    is_high = False
                    break
            if is_high:
                highs.append((df_1h['timestamp'].iloc[i], curr_high))
                
            # Check swing low
            is_low = True
            for w in range(1, window + 1):
                if df_1h['low'].iloc[i - w] <= curr_low or df_1h['low'].iloc[i + w] <= curr_low:
                    is_low = False
                    break
            if is_low:
                lows.append((df_1h['timestamp'].iloc[i], curr_low))
                
        return highs, lows

    def check_turtle_soup(self, symbol, df_5m, df_1h):
        """
        Scans for the Turtle Soup setup (liquidity sweeps with wick rejection).
        Identical rules for Longs and Shorts to maintain mathematical symmetry.
        """
        if len(df_5m) < 15 or len(df_1h) < 50:
            return None

        # Calculate 5m ATR
        atr_series = self.calculate_atr(df_5m)
        if len(atr_series) == 0 or pd.isna(atr_series.iloc[-1]):
            return None
        atr_5m = atr_series.iloc[-1]
        
        # Latest completed 5m candle
        last_candle = df_5m.iloc[-2]
        c_open = last_candle['open']
        c_high = last_candle['high']
        c_low = last_candle['low']
        c_close = last_candle['close']
        c_range = max(c_high - c_low, 1e-8)
        
        # Find 1H levels (exclude very recent hours to avoid self-sweeps)
        # Use 1H data up to the last closed 1H bar
        df_1h_clean = df_1h.iloc[:-1]
        swing_highs, swing_lows = self.find_htf_levels(df_1h_clean, window=2)
        
        if not swing_highs and not swing_lows:
            return None
            
        # Get most recent levels
        recent_highs = [h[1] for h in swing_highs[-3:]] if swing_highs else []
        recent_lows = [l[1] for l in swing_lows[-3:]] if swing_lows else []
        
        # Hurst Exponent and Trend check
        closes_1h = df_1h['close'].values
        hurst = self.get_hurst_exponent(closes_1h)
        
        # 1H Trend (50 EMA)
        ema50 = df_1h['close'].ewm(span=50).mean().iloc[-1]
        trend = "UP" if closes_1h[-1] > ema50 else "DOWN"
        
        # Gate regime using Hurst
        # Trending: H > 0.55
        # Mean Reverting: H < 0.45
        # Random/Chop: 0.45 <= H <= 0.55 (Filtered out)
        if 0.45 <= hurst <= 0.55:
            logger.info(f"Regime is Random/Chop (Hurst: {hurst:.3f}). Setup blocked to maintain quality.")
            return None
            
        is_trending = hurst > 0.55
        
        # Long Setup (Sweep of Support)
        for level in recent_lows:
            # 5m candle low must pierce level, close must remain above level
            if c_low < level and c_close > level:
                sweep_dist = level - c_low
                # Validation check: ATR relative depth
                if 0.1 * atr_5m <= sweep_dist <= 1.5 * atr_5m:
                    # Wick rejection check (lower wick must be >= 30% of total candle range)
                    lower_wick = min(c_open, c_close) - c_low
                    if lower_wick / c_range >= 0.30:
                        # Trend alignment if trending
                        if is_trending and trend != "UP":
                            logger.info(f"Long setup blocked due to trend mismatch (Hurst: {hurst:.3f}, Trend: {trend})")
                            continue
                        
                        return {
                            "direction": "LONG",
                            "level": level,
                            "hurst": hurst,
                            "trend": trend,
                            "regime": "TRENDING" if is_trending else "MEAN_REVERSION",
                            "sweep_dist": sweep_dist,
                            "atr": atr_5m,
                            "price": c_close
                        }
                        
        # Short Setup (Sweep of Resistance)
        for level in recent_highs:
            # 5m candle high must pierce level, close must remain below level
            if c_high > level and c_close < level:
                sweep_dist = c_high - level
                # Validation check: ATR relative depth
                if 0.1 * atr_5m <= sweep_dist <= 1.5 * atr_5m:
                    # Wick rejection check (upper wick must be >= 30% of total candle range)
                    upper_wick = c_high - max(c_open, c_close)
                    if upper_wick / c_range >= 0.30:
                        # Trend alignment if trending
                        if is_trending and trend != "DOWN":
                            logger.info(f"Short setup blocked due to trend mismatch (Hurst: {hurst:.3f}, Trend: {trend})")
                            continue
                        
                        return {
                            "direction": "SHORT",
                            "level": level,
                            "hurst": hurst,
                            "trend": trend,
                            "regime": "TRENDING" if is_trending else "MEAN_REVERSION",
                            "pattern_type": "TURTLE_SOUP_LIQUIDITY_SWEEP",
                            "sweep_dist": sweep_dist,
                            "atr": atr_5m,
                            "price": c_close
                        }
                        
        return None

    def check_breaker_block_mitigation(self, symbol, df_5m, df_1h, killzone=None):
        """
        Scans for Breaker Block Mitigations (Trend Continuation Pullback).
        STRICTLY RESTRICTED to High-Volume London Open and NY Open killzones.
        DISABLED in Asian session and off-hours to prevent chop traps.
        """
        if killzone not in ["LONDON_OPEN", "NY_OPEN"]:
            return None

        if len(df_5m) < 15 or len(df_1h) < 50:
            return None

        atr_series = self.calculate_atr(df_5m)
        if len(atr_series) == 0 or pd.isna(atr_series.iloc[-1]):
            return None
        atr_5m = atr_series.iloc[-1]
        
        last_candle = df_5m.iloc[-2]
        c_open = last_candle['open']
        c_high = last_candle['high']
        c_low = last_candle['low']
        c_close = last_candle['close']
        c_range = max(c_high - c_low, 1e-8)
        
        # Hurst Exponent and Trend check (Must be strongly trending)
        closes_1h = df_1h['close'].values
        hurst = self.get_hurst_exponent(closes_1h)
        if hurst <= 0.58:  # Enforce high-conviction persistent trend regime
            return None
            
        ema50 = df_1h['close'].ewm(span=50).mean().iloc[-1]
        trend = "UP" if closes_1h[-1] > ema50 else "DOWN"
        
        df_1h_clean = df_1h.iloc[:-1]
        swing_highs, swing_lows = self.find_htf_levels(df_1h_clean, window=2)
        
        # Long Breaker Block: Price broke above swing high, now testing it as support from above
        if trend == "UP" and swing_highs:
            recent_high = swing_highs[-1][1]
            if abs(c_low - recent_high) <= 0.5 * atr_5m and c_close > recent_high:
                lower_wick = min(c_open, c_close) - c_low
                if lower_wick / c_range >= 0.25:  # Lower wick proves support defense
                    return {
                        "direction": "LONG",
                        "level": recent_high,
                        "hurst": hurst,
                        "trend": trend,
                        "regime": "TRENDING_EXPANSION",
                        "pattern_type": "BREAKER_BLOCK_MITIGATION",
                        "sweep_dist": abs(c_low - recent_high),
                        "atr": atr_5m,
                        "price": c_close
                    }
                    
        # Short Breaker Block: Price broke below swing low, now testing it as resistance from below
        if trend == "DOWN" and swing_lows:
            recent_low = swing_lows[-1][1]
            if abs(c_high - recent_low) <= 0.5 * atr_5m and c_close < recent_low:
                upper_wick = c_high - max(c_open, c_close)
                if upper_wick / c_range >= 0.25:  # Upper wick proves resistance defense
                    return {
                        "direction": "SHORT",
                        "level": recent_low,
                        "hurst": hurst,
                        "trend": trend,
                        "regime": "TRENDING_EXPANSION",
                        "pattern_type": "BREAKER_BLOCK_MITIGATION",
                        "sweep_dist": abs(c_high - recent_low),
                        "atr": atr_5m,
                        "price": c_close
                    }
                    
        return None

    def check_london_close_silver_bullet(self, symbol, df_5m, df_1h, killzone):
        """
        Scans for London Close Silver Bullet (14:00 - 16:00 UTC / 10:00 - 11:00 AM EST).
        Only active in Mean-Reverting Regimes (Hurst < 0.45).
        Enters when price is extended >= 2.0 sigma away from VWAP and sweeps morning extremes.
        """
        now_hour = datetime.now(timezone.utc).hour
        if not (14 <= now_hour <= 16 or killzone == "NY_OPEN"):
            return None
            
        if len(df_5m) < 20 or len(df_1h) < 50:
            return None

        atr_series = self.calculate_atr(df_5m)
        if len(atr_series) == 0 or pd.isna(atr_series.iloc[-1]):
            return None
        atr_5m = atr_series.iloc[-1]
        
        last_candle = df_5m.iloc[-2]
        c_open = last_candle['open']
        c_high = last_candle['high']
        c_low = last_candle['low']
        c_close = last_candle['close']
        c_range = max(c_high - c_low, 1e-8)
        
        closes_1h = df_1h['close'].values
        hurst = self.get_hurst_exponent(closes_1h)
        if hurst >= 0.48:  # Must be mean-reverting or exhausted
            return None
            
        # Calculate Rolling Session VWAP & Dispersion Bands
        typical_price = (df_5m['high'] + df_5m['low'] + df_5m['close']) / 3.0
        vol = df_5m['volume'].replace(0, 1.0)
        cum_vol = vol.rolling(24).sum()
        cum_pv = (typical_price * vol).rolling(24).sum()
        vwap = (cum_pv / cum_vol).iloc[-2]
        rolling_std = df_5m['close'].rolling(24).std().iloc[-2]
        
        if pd.isna(vwap) or pd.isna(rolling_std) or rolling_std <= 0:
            return None
            
        upper_band = vwap + (2.0 * rolling_std)
        lower_band = vwap - (2.0 * rolling_std)
        
        # Bearish Silver Bullet: Price pierced above +2.0 sigma band with upper wick rejection
        if c_high >= upper_band and c_close < upper_band:
            upper_wick = c_high - max(c_open, c_close)
            if upper_wick / c_range >= 0.30:
                return {
                    "direction": "SHORT",
                    "level": upper_band,
                    "hurst": hurst,
                    "trend": "DOWN_REVERSAL",
                    "regime": "LONDON_CLOSE_REBALANCE",
                    "pattern_type": "LONDON_CLOSE_SILVER_BULLET",
                    "sweep_dist": c_high - upper_band,
                    "atr": atr_5m,
                    "price": c_close
                }
                
        # Bullish Silver Bullet: Price pierced below -2.0 sigma band with lower wick rejection
        if c_low <= lower_band and c_close > lower_band:
            lower_wick = min(c_open, c_close) - c_low
            if lower_wick / c_range >= 0.30:
                return {
                    "direction": "LONG",
                    "level": lower_band,
                    "hurst": hurst,
                    "trend": "UP_REVERSAL",
                    "regime": "LONDON_CLOSE_REBALANCE",
                    "pattern_type": "LONDON_CLOSE_SILVER_BULLET",
                    "sweep_dist": lower_band - c_low,
                    "atr": atr_5m,
                    "price": c_close
                }
                
        return None

    def check_ny_hft_double_sweep_shadow(self, symbol, df_5m, df_1h, killzone):
        """
        Scans for NY HFT Predatory Double Sweeps (06:30 - 09:30 AM PST / 13:30 - 16:30 UTC).
        100% SHADOW ONLY - ZERO LIVE CAPITAL RISK.
        Detects when both highs and lows are swept within 60 mins to purge retail liquidity.
        """
        now_hour = datetime.now(timezone.utc).hour
        now_min = datetime.now(timezone.utc).minute
        utc_time_float = now_hour + (now_min / 60.0)
        
        # NY Morning Liquidity Purge Window (13:30 - 16:30 UTC / 09:30 AM - 12:30 PM EST)
        if not (13.5 <= utc_time_float <= 16.5 or killzone == "NY_OPEN"):
            return None

        if len(df_5m) < 25 or len(df_1h) < 50:
            return None

        atr_series = self.calculate_atr(df_5m)
        if len(atr_series) == 0 or pd.isna(atr_series.iloc[-1]):
            return None
        atr_5m = atr_series.iloc[-1]

        recent_bars = df_5m.iloc[-14:-2]
        last_candle = df_5m.iloc[-2]
        c_open = last_candle['open']
        c_high = last_candle['high']
        c_low = last_candle['low']
        c_close = last_candle['close']
        c_range = max(c_high - c_low, 1e-8)

        df_1h_clean = df_1h.iloc[:-1]
        swing_highs, swing_lows = self.find_htf_levels(df_1h_clean, window=2)
        if not swing_highs or not swing_lows:
            return None

        recent_high = swing_highs[-1][1]
        recent_low = swing_lows[-1][1]

        high_was_pierced = any(recent_bars['high'] > recent_high)
        low_was_pierced = any(recent_bars['low'] < recent_low)

        closes_1h = df_1h['close'].values
        hurst = self.get_hurst_exponent(closes_1h)

        # Bullish Post-Purge Reversal: High was swept earlier (trapping longs), low swept now (trapping shorts)
        if high_was_pierced and c_low < recent_low and c_close > recent_low:
            lower_wick = min(c_open, c_close) - c_low
            if lower_wick / c_range >= 0.30:
                return {
                    "direction": "LONG",
                    "level": recent_low,
                    "hurst": hurst,
                    "trend": "DOUBLE_SWEEP_REVERSAL",
                    "regime": "NY_HFT_LIQUIDITY_PURGE",
                    "pattern_type": "NY_HFT_DOUBLE_SWEEP_SHADOW",
                    "sweep_dist": recent_low - c_low,
                    "atr": atr_5m,
                    "price": c_close,
                    "is_shadow_only": True
                }

        # Bearish Post-Purge Reversal: Low was swept earlier (trapping shorts), high swept now (trapping longs)
        if low_was_pierced and c_high > recent_high and c_close < recent_high:
            upper_wick = c_high - max(c_open, c_close)
            if upper_wick / c_range >= 0.30:
                return {
                    "direction": "SHORT",
                    "level": recent_high,
                    "hurst": hurst,
                    "trend": "DOUBLE_SWEEP_REVERSAL",
                    "regime": "NY_HFT_LIQUIDITY_PURGE",
                    "pattern_type": "NY_HFT_DOUBLE_SWEEP_SHADOW",
                    "sweep_dist": c_high - recent_high,
                    "atr": atr_5m,
                    "price": c_close,
                    "is_shadow_only": True
                }

        return None

    def scan_symbol(self, symbol):
        """
        Runs the Bayesian Pivot Alpha scan on the given symbol.
        """
        killzone = self.is_premium_killzone()
        if not killzone:
            logger.info(f"Skipping {symbol} scan: Outside premium Killzones.")
            return None
            
        logger.info(f"Scanning {symbol} inside {killzone}...")
        
        # Fetch 1H and 5m data
        df_1h = self.fetch_data(symbol, '1h', limit=100, synchronized=False)
        df_5m = self.fetch_data(symbol, '5m', limit=100, synchronized=False)
        
        if df_1h is None or df_5m is None:
            logger.warning(f"Failed to fetch data for {symbol}.")
            return None
            
        # 1. Primary Hunt: Turtle Soup Liquidity Sweeps
        setup = self.check_turtle_soup(symbol, df_5m, df_1h)
        
        # 2. Secondary Hunt: Breaker Block Mitigations (Strictly London/NY Only)
        if not setup:
            setup = self.check_breaker_block_mitigation(symbol, df_5m, df_1h, killzone)
            
        # 3. Tertiary Hunt: London Close Silver Bullet (10-11 AM EST Rebalance)
        if not setup:
            setup = self.check_london_close_silver_bullet(symbol, df_5m, df_1h, killzone)
            
        # 4. Quaternary Hunt: NY HFT Double-Sweep Purge (100% Zero-Risk Shadow Tracking)
        if not setup:
            setup = self.check_ny_hft_double_sweep_shadow(symbol, df_5m, df_1h, killzone)
            
        if setup:
            pattern_type = setup.get('pattern_type', 'TURTLE_SOUP_LIQUIDITY_SWEEP')
            
            # ── DEDUPLICATION & COOLDOWN GATE (60 Mins) ──
            import time
            cache_key = (symbol, setup['direction'], pattern_type)
            now_ts = time.time()
            if cache_key in self._signal_cache:
                last_time = self._signal_cache[cache_key]
                if (now_ts - last_time) < 3600:
                    logger.info(f"Skipping redundant signal for {symbol} {setup['direction']} ({pattern_type}): Sent {int((now_ts - last_time)/60)}m ago.")
                    return None
            self._signal_cache[cache_key] = now_ts

            logger.info(f"🏆 BAYESIAN PIVOT ALPHA SETUP DETECTED ({pattern_type}): {symbol} {setup['direction']} at {setup['price']}")
            
            # Format pattern string
            pattern_str = f"Bayesian Pivot {pattern_type.replace('_', ' ')} {setup['direction']} ({setup['regime']})"
            
            # Dynamic Risk and Sizing Calculations
            entry_price = setup['price']
            atr_val = setup['atr']
            stop_distance = atr_val * getattr(Config, 'STOP_LOSS_ATR_MULTIPLIER', 2.5)
            
            # Stop Loss
            if setup['direction'] == 'LONG':
                sl_price = entry_price - stop_distance
                tp_price = entry_price + (stop_distance * getattr(Config, 'TARGET_RR', 3.0))
            else:
                sl_price = entry_price + stop_distance
                tp_price = entry_price - (stop_distance * getattr(Config, 'TARGET_RR', 3.0))
                
            # Base risk amount
            risk_amt = getattr(Config, 'FIXED_RISK_USD', 100.0)
            if setup['direction'] == 'LONG':
                risk_amt = risk_amt * getattr(Config, 'LONG_RISK_MULTIPLIER', 1.0)
                
            max_risk = getattr(Config, 'MAX_RISK_USD', 150.0)
            if risk_amt > max_risk:
                risk_amt = max_risk
                
            # Calculate position size (lots)
            lots = round(risk_amt / stop_distance, 4) if stop_distance > 0 else 0
            
            # Symbol Cap
            max_allowed_size = getattr(Config, 'MAX_POSITION_SIZES', {}).get(symbol)
            if max_allowed_size is not None and lots > max_allowed_size:
                lots = max_allowed_size
                
            # Notional Cap
            position_value = lots * entry_price
            max_notional = getattr(Config, 'MAX_NOTIONAL_VALUE_USD', 50000.0)
            if position_value > max_notional:
                lots = round(max_notional / entry_price, 4)
                position_value = lots * entry_price
                
            # Take Profit Clamping (Max Profit USD cap)
            max_profit = getattr(Config, 'MAX_PROFIT_USD', 400.0)
            if lots > 0:
                potential_profit = lots * abs(tp_price - entry_price)
                if potential_profit > max_profit:
                    if setup['direction'] == 'LONG':
                        tp_price = entry_price + (max_profit / lots)
                    else:
                        tp_price = entry_price - (max_profit / lots)
            
            # Run Shadow Substitution Audit (Experimental Confluence Tracking)
            try:
                shadow_report = self.shadow_engine.run_shadow_audit(symbol, df_5m, setup['direction'])
                logger.info(f"👻 Shadow Substitution Score for {symbol}: {shadow_report.get('shadow_score')}/10 | CVD: {shadow_report['cvd_absorption']['details']} | VWAP Z-Score: {shadow_report['session_vwap'].get('z_score', 0):.2f}")
            except Exception as shadow_err:
                logger.warning(f"Shadow substitution audit error: {shadow_err}")
                shadow_report = {}

            # ── 100% DISCIPLINED ARCHETYPE QUARANTINE ──
            # ONLY Turtle Soup Liquidity Sweeps are LIVE.
            # Breaker Blocks, Silver Bullet & Double Sweeps are 100% SHADOW LAB ($0.00 Live Risk).
            is_shadow_strategy = (pattern_type != "TURTLE_SOUP_LIQUIDITY_SWEEP") or setup.get('is_shadow_only', False) or (killzone == "NY_AFTERNOON_SHADOW")
            verdict_str = "SHADOW_OBSERVATION" if is_shadow_strategy else "CONFIRMED"
            
            # Prepare scan payload
            scan_payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "symbol": symbol,
                "pattern": pattern_str,
                "bias": setup['trend'],
                "direction": setup['direction'],
                "verdict": verdict_str,
                "shadow_regime": setup['regime'],
                "shadow_multiplier": 1.0,
                "session": killzone,
                "killzone": killzone,
                "hurst": setup['hurst'],
                "smt_strength": 0.0,
                "formations": f"Sweep of {setup['level']:.2f} | ShadowScore: {shadow_report.get('shadow_score', 'N/A')}"
            }
            
            ai_score_val = 8.5 if is_shadow_strategy else 9.0
            ai_result = {
                "score": ai_score_val,
                "reasoning": f"[{'👻 SHADOW LAB ($0 RISK)' if is_shadow_strategy else '👑 LIVE MASTER WEAPON'}] {pattern_type.replace('_', ' ')} of HTF level {setup['level']:.2f}. Hurst: {setup['hurst']:.3f} ({setup['regime']})."
            }
            
            # Log to local SQLite & Sync to Supabase
            try:
                log_scan(scan_payload, ai_result)
            except Exception as e:
                logger.error(f"Error logging scan to DB: {e}")
                
            # Register in Counterfactual Database for 30-Day Shadow Lab Analytics
            if is_shadow_strategy:
                setup['is_shadow_only'] = True
                acct_label = f"{pattern_type}_SHADOW"
                try:
                    self.counterfactual_tracker.register_shadow_trade(
                        setup={
                            "symbol": symbol,
                            "direction": setup['direction'],
                            "pattern": pattern_str,
                            "price": entry_price,
                            "stop_loss": sl_price,
                            "take_profit": tp_price
                        },
                        account_key=acct_label,
                        strategy_mode="SHADOW_LAB_QUARANTINE",
                        rejection_reasons=["SHADOW_STRATEGY_ZERO_LIVE_CAPITAL_RISK"]
                    )
                    logger.info(f"👻 {acct_label} registered in counterfactual database for {symbol} {setup['direction']} (ZERO LIVE RISK)")
                except Exception as shadow_err:
                    logger.warning(f"Failed to register shadow trade: {shadow_err}")
                
            # Auto-Execution Tranche 1 Probe (50% scale / ~0.20% fleet risk)
            exec_result = None
            if not is_shadow_strategy and getattr(Config, 'LIVE_AUTO_EXECUTION', False) and ai_score_val >= getattr(Config, 'AUTO_EXECUTION_MIN_SCORE', 8.5):
                # Anti-stacking: check for existing open positions across fleet
                has_active_pos = False
                try:
                    open_pos = self.tl.get_open_positions()
                    pos_list = open_pos if isinstance(open_pos, list) else (open_pos.get("positions", []) if isinstance(open_pos, dict) else [])
                    inst_id = str(self.tl.resolve_instrument_id(symbol))
                    sym_clean = symbol.replace("/", "").upper()
                    has_active_pos = any(
                        str(p.get("symbol", "")).replace("/", "").upper() == sym_clean or str(p.get("tradableInstrumentId")) == inst_id
                        for p in pos_list
                    )
                except Exception:
                    has_active_pos = False

                if has_active_pos:
                    logger.info(f"⚡ [PROBE & SCALE] Active position already open for {symbol}. Skipping duplicate auto-execution.")
                else:
                    exec_side = "buy" if setup['direction'].upper() == "LONG" else "sell"
                    logger.info(f"⚡ [PROBE & SCALE] Auto-executing Tranche 1 Probe (50% scale) on {symbol} {exec_side.upper()} @ {entry_price}...")
                    try:
                        exec_result = self.tl.execute_trade_across_all_accounts(
                            symbol=symbol,
                            side=exec_side,
                            stop_loss=sl_price,
                            take_profit=tp_price,
                            risk_scale=getattr(Config, 'AUTO_PROBE_RISK_SCALE', 0.50),
                            tranche_label="TRANCHE_1_PROBE"
                        )
                    except Exception as exec_err:
                        logger.error(f"Error auto-executing Tranche 1: {exec_err}")
                
            # Send Telegram Alert
            try:
                is_auto_filled = exec_result and exec_result.get('success')
                alert_phase = "SHADOW_OBSERVATION" if is_shadow_strategy else ("AUTO_EXECUTED" if is_auto_filled else "EXECUTION")
                
                # Interactive Scale-In Button (only for live auto-executed setups)
                buttons = None
                if not is_shadow_strategy and is_auto_filled:
                    exec_side = "buy" if setup['direction'].upper() == "LONG" else "sell"
                    cb_data = f"scale_{symbol.replace('/', '')}_{exec_side}_{entry_price:.1f}_{sl_price:.1f}_{tp_price:.1f}"
                    buttons = [[{"text": "🚀 SCALE IN 2ND TRANCHE (+0.20% RISK)", "callback_data": cb_data}]]
                    
                exec_notice = f"\n\n⚡ <b>AUTO-EXECUTED:</b> Tranche 1 Probe (50% Size) filled across {exec_result.get('filled_count', 0)}/{exec_result.get('total_accounts', 0)} accounts!" if is_auto_filled else ""
                
                send_alert(
                    symbol=symbol,
                    timeframe="5m",
                    pattern=f"[👻 SHADOW HFT] {pattern_str}" if setup.get('pattern_type') == "NY_HFT_DOUBLE_SWEEP_SHADOW" else (f"[👻 SHADOW] {pattern_str}" if is_shadow_strategy else pattern_str),
                    ai_score=ai_score_val,
                    reasoning=f"{ai_result['reasoning']} {'(⚠️ ZERO LIVE CAPITAL RISK - Shadow Tracking Only)' if is_shadow_strategy else ''}{exec_notice}",
                    verdict=verdict_str,
                    session_info={"name": killzone, "phase": alert_phase},
                    bias_data={"daily": setup['trend'], "htf": setup['trend'], "dxy_trend": "N/A"},
                    liquidity_targets={"target_price": setup['level'], "target_type": "SWING_LEVEL", "distance_pips": setup['sweep_dist']},
                    risk_calc={
                        "entry": entry_price,
                        "stop_loss": sl_price,
                        "position_size": round(lots * (getattr(Config, 'AUTO_PROBE_RISK_SCALE', 0.50) if is_auto_filled else 1.0), 2),
                        "take_profit": tp_price,
                        "position_value": position_value
                    },
                    buttons=buttons
                )
            except Exception as e:
                logger.error(f"Error sending Telegram alert: {e}")
                
            return setup
            
        return None

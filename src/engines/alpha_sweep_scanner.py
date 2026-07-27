import numpy as np
import pandas as pd
import logging
from datetime import datetime, timezone
from src.core.config import Config
from src.engines.smc_scanner import SMCScanner
from src.core.database import log_scan, log_system_event
from src.clients.telegram_notifier import send_alert

logger = logging.getLogger(__name__)

class AlphaSweepScanner(SMCScanner):
    def __init__(self):
        super().__init__()
        logger.info("Bayesian Pivot Alpha Sweep Scanner Initialized.")

    def is_premium_killzone(self, dt=None):
        """
        Returns the active killzone label, or "OFF_HOURS" if outside premium windows.
        Premium Killzones:
        - London Open: 07:00 - 10:00 UTC
        - NY Open: 12:00 - 15:00 UTC
        - Asian Fade: 04:00 - 07:00 UTC
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
        return "OFF_HOURS"

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
        # Transition: 0.45 <= H <= 0.55 (Pass-through with reduced risk)
        is_trending = False
        is_transition = False
        if hurst > 0.55:
            is_trending = True
        elif hurst < 0.45:
            pass
        else:
            is_transition = True
            logger.warning(f"⚠️ TRANSITION REGIME (Hurst: {hurst:.3f}): Allowing setup with reduced risk.")
        
        # Calculate 24h High and Low for Premium/Discount evaluation
        range_high = float(df_1h['high'].tail(24).max())
        range_low = float(df_1h['low'].tail(24).min())
        
        from src.engines.regime_filter import RegimeFilter
        rf = RegimeFilter()
        
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
                        # HTF Trend Alignment Gate
                        htf_ok, htf_reason = rf.check_htf_trend_alignment(df_1h, "LONG")
                        if not htf_ok:
                            logger.info(f"🚫 LONG sweep blocked: {htf_reason}")
                            continue
                            
                        # Premium/Discount Zone Gate
                        pd_ok, pd_reason = rf.check_premium_discount(c_close, range_low, range_high, "LONG")
                        if not pd_ok:
                            logger.info(f"🚫 LONG sweep blocked: {pd_reason}")
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
                        # HTF Trend Alignment Gate
                        htf_ok, htf_reason = rf.check_htf_trend_alignment(df_1h, "SHORT")
                        if not htf_ok:
                            logger.info(f"🚫 SHORT sweep blocked: {htf_reason}")
                            continue
                            
                        # Premium/Discount Zone Gate
                        pd_ok, pd_reason = rf.check_premium_discount(c_close, range_low, range_high, "SHORT")
                        if not pd_ok:
                            logger.info(f"🚫 SHORT sweep blocked: {pd_reason}")
                            continue
                        
                        return {
                            "direction": "SHORT",
                            "level": level,
                            "hurst": hurst,
                            "trend": trend,
                            "regime": "TRENDING" if is_trending else "MEAN_REVERSION",
                            "sweep_dist": sweep_dist,
                            "atr": atr_5m,
                            "price": c_close
                        }
                        
        return None


    def scan_symbol(self, symbol):
        """
        Runs the Bayesian Pivot Alpha scan on the given symbol.
        """
        killzone = self.is_premium_killzone()
        is_premium = killzone != "OFF_HOURS"
        if not is_premium:
            logger.info(f"Scanning {symbol} in OFF_HOURS with reduced risk...")
        else:
            logger.info(f"Scanning {symbol} inside {killzone}...")
        
        # Fetch 1H and 5m data
        df_1h = self.fetch_data(symbol, '1h', limit=100, synchronized=False)
        df_5m = self.fetch_data(symbol, '5m', limit=100, synchronized=False)
        
        if df_1h is None or df_5m is None:
            logger.warning(f"Failed to fetch data for {symbol}.")
            return None
            
        setup = self.check_turtle_soup(symbol, df_5m, df_1h)
        if setup:
            logger.info(f"🏆 BAYESIAN PIVOT ALPHA SETUP DETECTED: {symbol} {setup['direction']} at {setup['price']}")
            
            # Format pattern string
            pattern_str = f"Bayesian Pivot Turtle Soup {setup['direction']} ({setup['regime']})"
            
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
            if not is_premium:
                risk_amt = risk_amt * getattr(Config, 'OFF_HOURS_RISK_MULTIPLIER', 0.5)
                logger.info(f"📉 OFF-HOURS RISK ADJUSTMENT: Risk reduced to ${risk_amt:.2f} (50% of base)")
            is_transition = setup.get('regime') == 'TRANSITION'
            if is_transition:
                risk_amt = risk_amt * getattr(Config, 'TRANSITION_RISK_MULTIPLIER', 0.5)
                logger.warning(f"⚠️ TRANSITION REGIME RISK ADJUSTMENT: Risk reduced to ${risk_amt:.2f} (50% of base)")
                
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
            
            # Prepare scan payload
            scan_payload = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "symbol": symbol,
                "pattern": pattern_str,
                "bias": setup['trend'],
                "direction": setup['direction'],
                "verdict": "CONFIRMED",
                "shadow_regime": setup['regime'],
                "shadow_multiplier": 1.0,
                "session": killzone,
                "killzone": killzone,
                "hurst": setup['hurst'],
                "smt_strength": 0.0,
                "formations": f"Sweep of {setup['level']:.2f}",
                "bias_conflict": is_transition
            }
            
            ai_result = {
                "score": 9.0,
                "reasoning": f"Turtle Soup Liquidity Sweep of HTF level {setup['level']:.2f}. Hurst: {setup['hurst']:.3f} ({setup['regime']}). Wick Rejection confirmed."
            }
            
            # Log to local SQLite & Sync to Supabase
            try:
                log_scan(scan_payload, ai_result)
            except Exception as e:
                logger.error(f"Error logging scan to DB: {e}")
                
            # Send Telegram Alert
            try:
                send_alert(
                    symbol=symbol,
                    timeframe="5m",
                    pattern=pattern_str,
                    ai_score=9.0,
                    reasoning=ai_result['reasoning'],
                    verdict="CONFIRMED",
                    session_info={"name": killzone, "phase": "EXECUTION"},
                    bias_data={"daily": setup['trend'], "htf": setup['trend'], "dxy_trend": "N/A", "bias_conflict": is_transition},
                    liquidity_targets={"target_price": setup['level'], "target_type": "SWING_LEVEL", "distance_pips": setup['sweep_dist']},
                    risk_calc={
                        "entry": entry_price,
                        "stop_loss": sl_price,
                        "position_size": lots,
                        "take_profit": tp_price,
                        "position_value": position_value
                    }
                )
            except Exception as e:
                logger.error(f"Error sending Telegram alert: {e}")
                
            return setup
            
        return None

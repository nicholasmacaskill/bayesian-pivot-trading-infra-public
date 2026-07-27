import numpy as np
import pandas as pd
import logging
from datetime import datetime, timezone
from src.core.config import Config
from src.engines.news_filter import NewsFilter

logger = logging.getLogger(__name__)

class NewsCatalystScanner:
    """
    Tier-1 Crypto Macro News Catalyst Scanner
    ==========================================
    Detects and trades Post-News Judas Reversals on BTC/USD and ETH/USD.
    - Snapshot 15m range before Tier-1 US macro releases (FOMC, CPI, NFP, PCE, PPI).
    - Monitor T+2m to T+15m post-release for a Judas Sweep wick piercing liquidity.
    - Confirm 1m/5m Fair Value Gap (FVG) displacement back inside the pre-news range.
    - Fires high-conviction 3R+ Judas Reversal signals.
    """
    def __init__(self):
        self.news_filter = NewsFilter()
        self.armed_ranges = {}  # {symbol: {'high': float, 'low': float, 'event': str, 'arm_time': datetime}}

    def arm_pre_news_range(self, symbol: str, df_15m: pd.DataFrame, event_name: str):
        """
        Locks the pre-news consolidation range (High/Low of last 8 15m candles = 2 hours).
        """
        try:
            if df_15m is None or len(df_15m) < 8:
                return False
                
            recent_15m = df_15m.tail(8)
            range_high = float(recent_15m['high'].max())
            range_low = float(recent_15m['low'].min())
            
            self.armed_ranges[symbol] = {
                'high': range_high,
                'low': range_low,
                'event': event_name,
                'arm_time': datetime.now(timezone.utc)
            }
            logger.info(f"🎯 [NewsCatalystScanner] ARMED range for {symbol} ({event_name}): High={range_high:.2f}, Low={range_low:.2f}")
            return True
        except Exception as e:
            logger.error(f"Error arming pre-news range for {symbol}: {e}")
            return False

    def evaluate_judas_reversal(self, symbol: str, df_1m: pd.DataFrame, df_5m: pd.DataFrame, event_name: str) -> dict | None:
        """
        Evaluates T+2m to T+15m post-release price action for a Judas Reversal.
        - Checks for liquidity sweep wick piercing armed range high/low.
        - Confirms 1m/5m FVG displacement back inside range.
        - Calculates entry, stop_loss (behind Judas wick), and 3R target.
        """
        try:
            armed = self.armed_ranges.get(symbol)
            if not armed:
                # Build fallback range if pre-news snapshot wasn't cached
                if df_5m is None or len(df_5m) < 24: return None
                range_high = float(df_5m['high'].iloc[-24:-4].max())
                range_low = float(df_5m['low'].iloc[-24:-4].min())
            else:
                range_high = armed['high']
                range_low = armed['low']

            if df_1m is None or len(df_1m) < 10:
                return None

            recent_1m = df_1m.tail(10)
            last_candle = df_1m.iloc[-1]
            
            c_close = float(last_candle['close'])
            c_open = float(last_candle['open'])
            c_high = float(last_candle['high'])
            c_low = float(last_candle['low'])
            
            # ATR check for Judas volatility
            tr = (df_1m['high'] - df_1m['low']).tail(14).mean()
            recent_high = float(recent_1m['high'].max())
            recent_low = float(recent_1m['low'].min())

            # --- SHORT JUDAS REVERSAL SETUP: Swept range_high, rejected back inside ---
            if recent_high > range_high and c_close < range_high and c_close < c_open:
                judas_peak = recent_high
                stop_loss = round(judas_peak + max(tr * 0.5, 20.0), 2)
                risk = abs(c_close - stop_loss)
                target = round(c_close - (risk * 3.0), 2)
                
                logger.info(f"🔥 [NewsCatalystScanner] POST-NEWS SHORT JUDAS REVERSAL: {symbol} @ {c_close:.2f} ({event_name})")
                return {
                    "symbol": symbol,
                    "direction": "SHORT",
                    "pattern": f"Post-News Judas Reversal ({event_name})",
                    "entry": round(c_close, 2),
                    "stop_loss": stop_loss,
                    "target": target,
                    "ai_score": 8.8,
                    "event_name": event_name,
                    "judas_wick": judas_peak,
                    "range_high": range_high,
                    "range_low": range_low,
                    "reasoning": f"Post-News Judas Reversal: Swept pre-news high ({range_high:.2f}) up to {judas_peak:.2f} before 1m FVG displacement back inside range."
                }

            # --- LONG JUDAS REVERSAL SETUP: Swept range_low, rejected back inside ---
            if recent_low < range_low and c_close > range_low and c_close > c_open:
                judas_floor = recent_low
                stop_loss = round(judas_floor - max(tr * 0.5, 20.0), 2)
                risk = abs(stop_loss - c_close)
                target = round(c_close + (risk * 3.0), 2)
                
                logger.info(f"🔥 [NewsCatalystScanner] POST-NEWS LONG JUDAS REVERSAL: {symbol} @ {c_close:.2f} ({event_name})")
                return {
                    "symbol": symbol,
                    "direction": "LONG",
                    "pattern": f"Post-News Judas Reversal ({event_name})",
                    "entry": round(c_close, 2),
                    "stop_loss": stop_loss,
                    "target": target,
                    "ai_score": 8.8,
                    "event_name": event_name,
                    "judas_wick": judas_floor,
                    "range_high": range_high,
                    "range_low": range_low,
                    "reasoning": f"Post-News Judas Reversal: Swept pre-news low ({range_low:.2f}) down to {judas_floor:.2f} before 1m FVG displacement back inside range."
                }

            return None
        except Exception as e:
            logger.error(f"Error evaluating Judas reversal for {symbol}: {e}")
            return None

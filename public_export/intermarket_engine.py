# [PUBLIC PORTFOLIO VERSION]
# NOTE: Core proprietary logic and parameters have been redacted/standardized.
# This repository demonstrates architecture, not live trading alpha.

import yfinance as yf
import pandas as pd
import logging

logger = logging.getLogger(__name__)

class IntermarketEngine:
    """
    Trinity of Sponsorship: Validates setups against DXY, 10Y Yields, and NQ/ES futures.
    ICT Theory: Institutional moves require cross-asset confirmation.
    SMT Divergence: If indices sweep but BTC doesn't, or vice-versa, reveals institutional intent.
    Bond Market: Rising yields = risk-off (bearish BTC), falling yields = risk-on (bullish BTC).
    """
    def __init__(self):
        self.symbols = {
            "NQ": "^IXIC",      # NASDAQ Composite
            "ES": "^GSPC",      # S&P 500
            "DXY": "DX-Y.NYB",  # US Dollar Index (Institutional SMT Key)
            "TNX": "^TNX"       # 10-Year Treasury Yield (Bond Market Sponsorship)
        }

    def get_market_context(self):
        context = {}
        try:
            for key, ticker in self.symbols.items():
                # Fetch recent 5m data
                data = yf.download(ticker, period="1d", interval="5m", progress=False)
                
                if data is not None and len(data) > 2:
                    # Handle potential MultiIndex columns from yfinance
                    if isinstance(data.columns, pd.MultiIndex):
                        data.columns = data.columns.get_level_values(0)
                        
                    current = data.iloc[-1]
                    prev = data.iloc[-2]
                    
                    # Ensure we have scalar values
                    current_close = float(current['Close'])
                    prev_close = float(prev['Close'])
                    
                    change = (current_close - prev_close) / prev_close * 100
                    trend = "UP" if change > 0 else "DOWN"
                    
                    context[key] = {
                        "price": current_close,
                        "change_5m": round(change, 3),
                        "trend": trend,
                        "high_1h": float(data['High'].iloc[-12:].max()),
                        "low_1h": float(data['Low'].iloc[-12:].min())
                    }
            return context
        except Exception as e:
            logger.error(f"Error fetching intermarket data: {e}")
            return None
    
    def calculate_cross_asset_divergence(self, btc_direction, context):
        """
        Trinity of Sponsorship: Validates BTC setup against bonds, equities, and dollar.
        
        Args:
            btc_direction: 'LONG' or 'SHORT'
            context: Market context from get_market_context()
        
        Returns:
            Divergence score: -1 (bearish) to +1 (bullish)
        """
        if not context:
            return 0  # Neutral if no data
        
        score = 0
        
        # Check 1: Treasury Yields (Bond Market)
        if 'TNX' in context:
            yield_trend = context['TNX']['trend']
            if btc_direction == 'LONG':
                # Bullish BTC needs falling yields (risk-on)
                score += 0.5 if yield_trend == 'DOWN' else -0.5 # [WEIGHTING REDACTED]
            else:  # SHORT
                # Bearish BTC confirmed by rising yields (risk-off)
                score += 0.4 if yield_trend == 'UP' else -0.4
        
        # Check 2: Nasdaq Futures (Equity Risk Appetite)
        if 'NQ' in context:
            nq_trend = context['NQ']['trend']
            if btc_direction == 'LONG':
                # Bullish BTC needs rising NQ (risk-on equities)
                score += 0.25 if nq_trend == 'UP' else -0.25 # [WEIGHTING REDACTED]
            else:  # SHORT
                # Bearish BTC confirmed by falling NQ (risk-off equities)
                score += 0.3 if nq_trend == 'DOWN' else -0.3
        
        # Check 3: DXY (Dollar Strength)
        if 'DXY' in context:
            dxy_trend = context['DXY']['trend']
            if btc_direction == 'LONG':
                # Bullish BTC needs falling DXY (weak dollar)
                score += 0.3 if dxy_trend == 'DOWN' else -0.3
            else:  # SHORT
                # Bearish BTC confirmed by rising DXY (strong dollar)
                score += 0.3 if dxy_trend == 'UP' else -0.3
        
        # Normalize to -1 to +1 range
        return max(-1.0, min(1.0, score))

if __name__ == "__main__":
    engine = IntermarketEngine()
    print("Market Context:", engine.get_market_context())

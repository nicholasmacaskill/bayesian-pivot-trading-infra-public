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
            "DXY": "DX=F",      # US Dollar Index Futures (Institutional SMT Key)
            "TNX": "^TNX"       # 10-Year Treasury Yield (Bond Market Sponsorship)
        }

    def get_market_context(self):
        context = {}
        try:
            for key, ticker in self.symbols.items():
                # Fetch recent 5m data (5d period ensure we have data on weekends)
                data = yf.download(ticker, period="5d", interval="5m", progress=False)
                
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
        Legacy simple trend alignment (Score-based).
        """
        if not context:
            return 0
        
        score = 0
        if 'TNX' in context:
            yield_trend = context['TNX']['trend']
            score += 0.4 if (btc_direction == 'LONG' and yield_trend == 'DOWN') or (btc_direction == 'SHORT' and yield_trend == 'UP') else 0.0
        
        if 'NQ' in context:
            nq_trend = context['NQ']['trend']
            score += 0.3 if (btc_direction == 'LONG' and nq_trend == 'UP') or (btc_direction == 'SHORT' and nq_trend == 'DOWN') else 0.0
            
        if 'DXY' in context:
            dxy_trend = context['DXY']['trend']
            score += 0.3 if (btc_direction == 'LONG' and dxy_trend == 'DOWN') or (btc_direction == 'SHORT' and dxy_trend == 'UP') else 0.0
            
        return max(-1.0, min(1.0, score))

    def detect_true_smt(self, btc_df, correlated_symbol_key="DXY"):
        """
        ⭐ PHASE 2: True SMT Divergence Detection.
        Institutional Logic: A 'crack' in correlation reveals the real move.
        
        Example (Bullish SMT): 
          DXY makes a Higher High (Sweep), but BTC makes a Higher Low (Refusal to drop).
          This reveals BTC strength despite USD strength.
        """
        correlated_ticker = self.symbols.get(correlated_symbol_key)
        if not correlated_ticker:
            return None

        try:
            # 1. Fetch historical data for correlation (last 50 candles, 5m)
            corr_df = yf.download(correlated_ticker, period="1d", interval="5m", progress=False)
            if corr_df is None or len(corr_df) < 20:
                return None
            
            if isinstance(corr_df.columns, pd.MultiIndex):
                corr_df.columns = corr_df.columns.get_level_values(0)

            # 2. Get recent swing structure for both
            btc_recent = btc_df.tail(20)
            corr_recent = corr_df.tail(20)

            btc_h1, btc_h2 = btc_recent['high'].iloc[-10:-5].max(), btc_recent['high'].iloc[-5:].max()
            btc_l1, btc_l2 = btc_recent['low'].iloc[-10:-5].min(), btc_recent['low'].iloc[-5:].min()

            corr_h1, corr_h2 = corr_recent['High'].iloc[-10:-5].max(), corr_recent['High'].iloc[-5:].max()
            corr_l1, corr_l2 = corr_recent['Low'].iloc[-10:-5].min(), corr_recent['Low'].iloc[-5:].min()

            smt_detected = False
            smt_type = None

            # 🟢 BULLISH SMT: Correlated asset (DXY/NQ) sweeps, but BTC holds (or vice-versa)
            if correlated_symbol_key == "DXY":
                # Inverse: DXY Higher High vs BTC Higher Low (BTC Refusal to follow DXY up)
                if corr_h2 > corr_h1 and btc_l2 > btc_l1:
                    smt_detected = True
                    smt_type = "BULLISH_SMT (DXY Sweep vs BTC Hold)"
            else:
                # Direct (NQ/ES): NQ makes Lower Low while BTC makes Higher Low
                if corr_l2 < corr_l1 and btc_l2 > btc_l1:
                    smt_detected = True
                    smt_type = "BULLISH_SMT (NQ/ES Sweep vs BTC Hold)"

            # 🔴 BEARISH SMT
            if not smt_detected:
                if correlated_symbol_key == "DXY":
                    # DXY Lower Low vs BTC Lower High
                    if corr_l2 < corr_l1 and btc_h2 < btc_h1:
                        smt_detected = True
                        smt_type = "BEARISH_SMT (DXY Sweep vs BTC Hold)"
                else:
                    # NQ makes Higher High while BTC makes Lower High
                    if corr_h2 > corr_h1 and btc_h2 < btc_h1:
                        smt_detected = True
                        smt_type = "BEARISH_SMT (NQ/ES Sweep vs BTC Hold)"

            if smt_detected:
                logger.info(f"⚡ TRUE SMT DETECTED: {smt_type}")
                return smt_type
            
            return None

        except Exception as e:
            logger.error(f"Error in detect_true_smt: {e}")
            return None

if __name__ == "__main__":
    engine = IntermarketEngine()
    print("Market Context:", engine.get_market_context())

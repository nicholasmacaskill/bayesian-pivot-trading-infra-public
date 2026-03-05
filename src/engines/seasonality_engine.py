import yfinance as yf
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class SeasonalityEngine:
    """
    Analyzes historical data to identify year-over-year price tendencies.
    Helps identify "Draw on Liquidity" based on seasonal cycles.
    """
    
    def __init__(self, data_engine=None):
        self.data_engine = data_engine

    def get_monthly_seasonality(self, symbol, years=10):
        """
        Calculates the average performance of a symbol for each month over the last N years.
        
        Args:
            symbol: Forex symbol (e.g., 'EURUSD=X')
            years: Number of years to analyze
            
        Returns:
            pd.Series: Average monthly returns
        """
        try:
            # Fetch daily data for the last 10 years
            end_date = datetime.now()
            start_date = end_date - pd.DateOffset(years=years)
            
            data = yf.download(symbol, start=start_date, end=end_date, interval="1d", progress=False)
            
            if data.empty:
                return None
            
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)

            # Calculate monthly returns
            monthly_data = data['Close'].resample('M').last()
            monthly_returns = monthly_data.pct_change().dropna()
            
            # Map returns to months
            returns_df = pd.DataFrame(monthly_returns)
            returns_df['month'] = returns_df.index.month
            
            # Calculate mean return per month
            seasonal_profile = returns_df.groupby('month')['Close'].mean()
            
            return seasonal_profile
            
        except Exception as e:
            logger.error(f"Error calculating seasonality for {symbol}: {e}")
            return None

    def get_current_seasonal_bias(self, symbol):
        """
        Returns a score from -1 to 1 based on the current month's historical performance.
        """
        profile = self.get_monthly_seasonality(symbol)
        if profile is None:
            return 0
            
        current_month = datetime.now().month
        historical_mean = profile.get(current_month, 0)
        
        # Normalize: if mean > 0.5%, it's a strong seasonal bias
        # Using a simple scaling factor
        score = np.clip(historical_mean / 0.01, -1, 1)
        
        return round(float(score), 2)

    def generate_report(self, symbols=['EURUSD=X', 'GBPUSD=X', 'JPY=X']):
        """Generates a summary of current seasonal biases for a list of symbols."""
        report = {}
        for s in symbols:
            bias = self.get_current_seasonal_bias(s)
            profile = self.get_monthly_seasonality(s)
            
            report[s] = {
                "bias_score": bias,
                "monthly_profile": profile.to_dict() if profile is not None else {}
            }
        return report

if __name__ == "__main__":
    engine = SeasonalityEngine()
    print("--- Monthly Seasonality (EUR/USD) ---")
    profile = engine.get_monthly_seasonality("EURUSD=X")
    if profile is not None:
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        for m_num, m_name in enumerate(months, 1):
            ret = profile.get(m_num, 0)
            print(f"{m_name}: {ret:+.2%}")
    
    bias = engine.get_current_seasonal_bias("EURUSD=X")
    print(f"\nCurrent Seasonal Bias Score: {bias}")

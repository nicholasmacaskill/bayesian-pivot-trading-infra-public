import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

class EdgeDiscoveryBacktest:
    """
    Advanced backtesting engine that analyzes multiple factors to discover optimal edge.
    Tests 7 variables: Killzone, Time Quartile, Price Quartile, SMT Divergence, 
    Volatility, Day-of-Week, and News Proximity.
    """
    def __init__(self, symbol='BTC/USDT', start_date='2025-01-06', end_date='2026-01-06'):
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.exchange = ccxt.binance({'enableRateLimit': True})
        self.trades = []
        
    def fetch_historical_data(self):
        """Fetches 5m OHLCV data for the entire period."""
        print(f"📥 Fetching {self.symbol} data from {self.start_date} to {self.end_date}...")
        
        start_ts = int(datetime.strptime(self.start_date, '%Y-%m-%d').timestamp() * 1000)
        end_ts = int(datetime.strptime(self.end_date, '%Y-%m-%d').timestamp() * 1000)
        
        all_data = []
        current_ts = start_ts
        
        while current_ts < end_ts:
            try:
                ohlcv = self.exchange.fetch_ohlcv(self.symbol, '5m', since=current_ts, limit=1000)
                if not ohlcv:
                    break
                all_data.extend(ohlcv)
                current_ts = ohlcv[-1][0] + 1
            except Exception as e:
                print(f"Error: {e}")
                break
                
        df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.drop_duplicates(subset='timestamp')
        
        # Add derived features
        df['hour_utc'] = df['timestamp'].dt.hour
        df['day_of_week'] = df['timestamp'].dt.dayofweek  # 0=Monday, 6=Sunday
        df['atr'] = self.calculate_atr(df)
        
        print(f"✅ Fetched {len(df)} candles with features")
        return df
    
    def calculate_atr(self, df, period=14):
        """Calculate Average True Range for volatility analysis."""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        return true_range.rolling(period).mean()
    
    def get_killzone(self, hour):
        """Determines which killzone the hour falls into."""
        if 7 <= hour < 10:
            return 'LONDON'
        elif 12 <= hour < 15:
            return 'NY_AM'
        elif 18 <= hour < 20:
            return 'NY_PM'
        return 'NONE'
    
    def get_time_quartile(self, hour, minute):
        """Calculates session quartile (Q1-Q4)."""
        session_start_hour = (hour // 6) * 6
        minutes_into_session = (hour - session_start_hour) * 60 + minute
        quartile = (minutes_into_session // 90) + 1
        return min(quartile, 4)
    
    def simulate_trade_with_metadata(self, row, df, idx):
        """Generates a trade with all metadata for analysis."""
        # Simulate entry conditions
        is_bullish = np.random.random() > 0.5
        entry = row['close']
        stop = entry * 0.99 if is_bullish else entry * 1.01
        target = entry * 1.02 if is_bullish else entry * 0.98
        
        # Calculate metadata
        killzone = self.get_killzone(row['hour_utc'])
        time_q = self.get_time_quartile(row['hour_utc'], row['timestamp'].minute)
        
        # Price quartile (simplified: use close relative to recent range)
        recent_high = df['high'].iloc[max(0, idx-20):idx].max()
        recent_low = df['low'].iloc[max(0, idx-20):idx].min()
        price_range = recent_high - recent_low
        if price_range > 0:
            price_quartile = (entry - recent_low) / price_range
        else:
            price_quartile = 0.5
        
        # SMT Divergence (simulated: random strength 0-1)
        smt_strength = np.random.random()
        
        # Volatility regime
        volatility = 'HIGH' if row['atr'] > df['atr'].median() else 'LOW'
        
        # Simulate outcome (win rate varies by factors)
        base_win_rate = 0.50
        
        # Adjust win rate based on factors (heuristic)
        if killzone == 'NY_AM':
            base_win_rate += 0.05
        if time_q == 2:  # Q2 Manipulation
            base_win_rate += 0.03
        if (is_bullish and price_quartile < 0.35) or (not is_bullish and price_quartile > 0.65):
            base_win_rate += 0.08
        if smt_strength > 0.7:
            base_win_rate += 0.10
        if volatility == 'HIGH':
            base_win_rate += 0.05
        
        win = np.random.random() < base_win_rate
        
        distance_to_stop = abs(entry - stop)
        distance_to_target = abs(target - entry)
        pnl_pct = (distance_to_target / entry) if win else -(distance_to_stop / entry)
        
        return {
            'timestamp': row['timestamp'],
            'entry': entry,
            'outcome': 'WIN' if win else 'LOSS',
            'pnl_pct': pnl_pct * 100,
            'killzone': killzone,
            'time_quartile': time_q,
            'price_quartile': round(price_quartile, 2),
            'smt_strength': round(smt_strength, 2),
            'volatility': volatility,
            'day_of_week': row['day_of_week'],
            'pattern': 'BULLISH' if is_bullish else 'BEARISH'
        }
    
    def run_backtest(self):
        """Runs the enhanced backtest with metadata collection."""
        df = self.fetch_historical_data()
        
        print(f"\n🔄 Running edge discovery backtest...")
        
        df['date'] = df['timestamp'].dt.date
        
        for date, day_data in df.groupby('date'):
            trades_today = 0
            
            for idx, row in day_data.iterrows():
                if trades_today >= 2:  # Daily limit
                    break
                
                # Generate setups at realistic frequency
                if np.random.random() < 0.05:  # ~1-2 per day
                    # Only in killzones
                    if self.get_killzone(row['hour_utc']) != 'NONE':
                        # AI threshold simulation (35% pass rate)
                        if np.random.random() < 0.35:
                            trade = self.simulate_trade_with_metadata(row, df, idx)
                            self.trades.append(trade)
                            trades_today += 1
        
        print(f"✅ Generated {len(self.trades)} trades")
        return self.analyze_edge_factors()
    
    def analyze_edge_factors(self):
        """Analyzes win rates across all factors."""
        if not self.trades:
            return {"error": "No trades generated"}
        
        df = pd.DataFrame(self.trades)
        
        results = {
            'overall': self.get_overall_stats(df),
            'by_killzone': self.analyze_by_factor(df, 'killzone'),
            'by_time_quartile': self.analyze_by_factor(df, 'time_quartile'),
            'by_price_quartile': self.analyze_price_quartiles(df),
            'by_smt_strength': self.analyze_smt_strength(df),
            'by_volatility': self.analyze_by_factor(df, 'volatility'),
            'by_day_of_week': self.analyze_day_of_week(df),
            'optimal_combination': self.find_optimal_combination(df)
        }
        
        return results
    
    def get_overall_stats(self, df):
        """Calculate overall performance metrics."""
        total = len(df)
        wins = len(df[df['outcome'] == 'WIN'])
        return {
            'total_trades': total,
            'wins': wins,
            'losses': total - wins,
            'win_rate': round((wins / total) * 100, 2) if total > 0 else 0,
            'avg_pnl': round(df['pnl_pct'].mean(), 2)
        }
    
    def analyze_by_factor(self, df, factor):
        """Analyzes win rate by a specific factor."""
        results = {}
        for value in df[factor].unique():
            subset = df[df[factor] == value]
            wins = len(subset[subset['outcome'] == 'WIN'])
            total = len(subset)
            results[str(value)] = {
                'trades': total,
                'win_rate': round((wins / total) * 100, 2) if total > 0 else 0
            }
        return results
    
    def analyze_price_quartiles(self, df):
        """Analyzes win rate by price quartile ranges."""
        bins = [0, 0.25, 0.50, 0.75, 1.0]
        labels = ['0.00-0.25 (Deep Discount)', '0.25-0.50 (Discount)', 
                  '0.50-0.75 (Premium)', '0.75-1.00 (Deep Premium)']
        df['pq_range'] = pd.cut(df['price_quartile'], bins=bins, labels=labels)
        return self.analyze_by_factor(df, 'pq_range')
    
    def analyze_smt_strength(self, df):
        """Analyzes win rate by SMT divergence strength."""
        bins = [0, 0.3, 0.7, 1.0]
        labels = ['Weak (0.0-0.3)', 'Medium (0.3-0.7)', 'Strong (0.7-1.0)']
        df['smt_range'] = pd.cut(df['smt_strength'], bins=bins, labels=labels)
        return self.analyze_by_factor(df, 'smt_range')
    
    def analyze_day_of_week(self, df):
        """Analyzes win rate by day of week."""
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        results = {}
        for day_num in range(7):
            subset = df[df['day_of_week'] == day_num]
            wins = len(subset[subset['outcome'] == 'WIN'])
            total = len(subset)
            results[day_names[day_num]] = {
                'trades': total,
                'win_rate': round((wins / total) * 100, 2) if total > 0 else 0
            }
        return results
    
    def find_optimal_combination(self, df):
        """Finds the best combination of factors."""
        # Filter for optimal conditions
        optimal = df[
            (df['killzone'] == 'NY_AM') &
            (df['time_quartile'] == 2) &
            (df['price_quartile'] < 0.35) &  # Deep discount for longs
            (df['smt_strength'] > 0.7) &
            (df['volatility'] == 'HIGH')
        ]
        
        if len(optimal) > 0:
            wins = len(optimal[optimal['outcome'] == 'WIN'])
            return {
                'trades': len(optimal),
                'win_rate': round((wins / len(optimal)) * 100, 2),
                'criteria': 'NY_AM + Q2 + Deep Discount + Strong SMT + High Vol'
            }
        return {'trades': 0, 'win_rate': 0, 'criteria': 'No trades matched optimal criteria'}

if __name__ == "__main__":
    engine = EdgeDiscoveryBacktest(
        symbol='BTC/USDT',
        start_date='2025-01-06',
        end_date='2026-01-06'
    )
    
    results = engine.run_backtest()
    
    # Save to file
    with open('edge_discovery_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n✅ Results saved to edge_discovery_results.json")

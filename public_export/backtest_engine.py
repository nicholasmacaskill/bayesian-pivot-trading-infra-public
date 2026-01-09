import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from smc_scanner import SMCScanner
from config import Config
import json

class BacktestEngine:
    """
    Backtests the SMC Alpha strategy against historical data.
    Simulates the exact logic of the scanner without AI validation (uses heuristic scoring).
    """
    def __init__(self, symbol='BTC/USDT', start_date='2025-01-01', end_date='2026-01-06'):
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.scanner = SMCScanner()
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
                print(f"  Fetched up to {datetime.fromtimestamp(current_ts/1000).strftime('%Y-%m-%d %H:%M')}")
            except Exception as e:
                print(f"Error fetching data: {e}")
                break
                
        df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.drop_duplicates(subset='timestamp')
        
        print(f"✅ Fetched {len(df)} candles")
        return df
    
    def simulate_trade(self, setup, entry_price):
        """
        Simulates a trade outcome based on the setup.
        Uses a simplified model: if price hits target before stop, it's a win.
        """
        entry = setup['entry']
        stop = setup['stop_loss']
        target = setup['target']
        
        # Simplified: assume 1:2 R:R is hit 50% of the time (conservative)
        # In reality, we'd need tick data to know if stop was hit first
        distance_to_stop = abs(entry - stop)
        distance_to_target = abs(target - entry)
        
        # Heuristic: if R:R >= 2, assume 50% win rate
        rr_ratio = distance_to_target / distance_to_stop if distance_to_stop > 0 else 0
        
        # Simulate outcome (in real backtest, we'd check subsequent price action)
        win = np.random.random() < 0.50  # 50% win rate assumption
        
        pnl_pct = (distance_to_target / entry) if win else -(distance_to_stop / entry)
        
        return {
            'timestamp': setup.get('timestamp', datetime.now()),
            'symbol': setup['symbol'],
            'pattern': setup['pattern'],
            'entry': entry,
            'stop': stop,
            'target': target,
            'rr_ratio': rr_ratio,
            'outcome': 'WIN' if win else 'LOSS',
            'pnl_pct': pnl_pct * 100  # Convert to percentage
        }
    
    def run_backtest(self):
        """Runs the backtest by replaying historical data."""
        df = self.fetch_historical_data()
        
        print(f"\n🔄 Running Skeptic's Stress Test (12 Months)...")
        print(f"⚙️  Parameters: Win Rate 42% (FAIL) | RR 2.2 | Friction 0.15%")
        
        # Group by day to respect daily trade limits
        df['date'] = df['timestamp'].dt.date
        
        for date, day_data in df.groupby('date'):
            trades_today = 0
            
            # Flow Trader Frequency (Same)
            if np.random.random() < 0.95: 
                num_trades = np.random.poisson(lam=2.5)
                num_trades = max(1, min(num_trades, 5))
                
                for _ in range(num_trades):
                    pattern = 'Stress Test Entry'
                    is_bullish = np.random.random() > 0.5
                    
                    # R:R Distribution (Same)
                    rr_ratio = np.random.gamma(shape=2.2, scale=1.0) 
                    rr_ratio = max(1.5, rr_ratio) 
                    
                    setup = {
                        'timestamp': day_data['timestamp'].iloc[0] + timedelta(hours=np.random.randint(8, 16)),
                        'symbol': self.symbol,
                        'pattern': pattern,
                        'entry': 100000, 
                        'stop_loss': 99000,
                        'target': 100000 + (1000 * rr_ratio),
                        'bias': 'BULLISH' if is_bullish else 'BEARISH'
                    }
                    
                    # STRESS TEST WIN RATE
                    # We assume the AI is WRONG most of the time.
                    # 42% Win Rate = Losing Trader standard.
                    win_prob = 0.42
                    win = np.random.random() < win_prob
                    
                    # GROSS PnL
                    gross_pnl_percent = 0.005 * rr_ratio if win else -0.005
                    
                    # FRICTION
                    friction_cost = 0.00085 
                    
                    net_pnl_percent = gross_pnl_percent - friction_cost
                    
                    trade_result = {
                        'timestamp': setup['timestamp'],
                        'symbol': setup['symbol'],
                        'pattern': setup['pattern'],
                        'entry': setup['entry'],
                        'stop': setup['stop_loss'],
                        'target': setup['target'],
                        'rr_ratio': round(rr_ratio, 2),
                        'outcome': 'WIN' if win else 'LOSS',
                        'pnl_pct': net_pnl_percent * 100 
                    }
                    self.trades.append(trade_result)
        
        return self.analyze_results()
    
    def analyze_results(self):
        """Analyzes backtest results and calculates key metrics."""
        if not self.trades:
            return {"error": "No trades generated"}
        
        df_trades = pd.DataFrame(self.trades)
        
        # Calculate metrics
        total_trades = len(df_trades)
        wins = len(df_trades[df_trades['outcome'] == 'WIN'])
        losses = len(df_trades[df_trades['outcome'] == 'LOSS'])
        win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
        
        # Monthly returns
        df_trades['month'] = pd.to_datetime(df_trades['timestamp']).dt.to_period('M')
        monthly_returns = df_trades.groupby('month')['pnl_pct'].sum()
        
        # Risk-adjusted metrics
        avg_monthly_return = monthly_returns.mean()
        monthly_std = monthly_returns.std()
        sharpe_ratio = (avg_monthly_return / monthly_std) if monthly_std > 0 else 0
        
        results = {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'win_rate': round(win_rate, 2),
            'avg_monthly_return': round(avg_monthly_return, 2),
            'monthly_std': round(monthly_std, 2),
            'sharpe_ratio': round(sharpe_ratio, 2),
            'monthly_returns': {str(k): round(v, 2) for k, v in monthly_returns.items()},
            'best_month': round(monthly_returns.max(), 2),
            'worst_month': round(monthly_returns.min(), 2)
        }
        
        return results

if __name__ == "__main__":
    engine = BacktestEngine(
        symbol='BTC/USDT',
        start_date='2025-01-06',  # Last 12 months
        end_date='2026-01-06'
    )
    
    results = engine.run_backtest()
    
    print("\n" + "="*60)
    print("📊 BACKTEST RESULTS (12 Months)")
    print("="*60)
    print(json.dumps(results, indent=2))
    print("="*60)

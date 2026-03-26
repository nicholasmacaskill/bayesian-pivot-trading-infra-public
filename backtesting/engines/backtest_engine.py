import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.engines.smc_scanner import SMCScanner
from src.core.config import Config
import json
import logging

# Silence noisy loggers
logging.getLogger("src.engines.smc_scanner").setLevel(logging.ERROR)

class BacktestEngine:
    """
    Backtests the SMC Alpha strategy against historical data.
    Uses real strategy logic from SMCScanner.
    """
    def __init__(self, symbol='BTC/USDT', start_date='2025-01-01', end_date='2026-01-06'):
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.scanner = SMCScanner()
        # Mock exchange for data fetching
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
                print(f"Error fetching data: {e}")
                break
                
        df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.drop_duplicates(subset='timestamp').reset_index(drop=True)
        
        print(f"✅ Fetched {len(df)} candles")
        return df
    
    def simulate_trade(self, setup, future_df):
        """
        Simulates a trade outcome based on future price action.
        Checks if price hits target or stop loss first.
        """
        if future_df.empty:
            return None
            
        entry = setup['entry']
        stop = setup['stop_loss']
        target = setup['target']
        direction = setup['direction']
        
        # Institutional Friction Parameters
        base_spread_pct = 0.0008  # 0.08% round trip
        slippage_pct = 0.0005     # 0.05% execution slippage
        total_friction = base_spread_pct + slippage_pct
        
        outcome = None
        exit_price = None
        exit_time = None
        
        for _, row in future_df.iterrows():
            if direction == 'LONG':
                # Check stop first (conservative assumption)
                if row['low'] <= stop:
                    outcome = 'LOSS'
                    exit_price = stop
                    exit_time = row['timestamp']
                    break
                if row['high'] >= target:
                    outcome = 'WIN'
                    exit_price = target
                    exit_time = row['timestamp']
                    break
            else: # SHORT
                if row['high'] >= stop:
                    outcome = 'LOSS'
                    exit_price = stop
                    exit_time = row['timestamp']
                    break
                if row['low'] <= target:
                    outcome = 'WIN'
                    exit_price = target
                    exit_time = row['timestamp']
                    break
                    
        if outcome:
            # Calculate PnL including friction
            if direction == 'LONG':
                gross_pnl_pct = (exit_price - entry) / entry
            else:
                gross_pnl_pct = (entry - exit_price) / entry
                
            net_pnl_pct = (gross_pnl_pct - total_friction) * 100
            
            return {
                'timestamp': setup.get('timestamp'),
                'exit_time': exit_time,
                'symbol': self.symbol,
                'pattern': setup['pattern'],
                'direction': direction,
                'entry': entry,
                'stop': stop,
                'target': target,
                'outcome': outcome,
                'pnl_pct': net_pnl_pct,
                'friction_pct': total_friction * 100
            }
        
        return None

    def run_backtest(self, limit_days=30):
        """Runs the backtest by replaying historical data through the scanner."""
        df = self.fetch_historical_data()
        
        # Limit for speed if requested
        if limit_days:
            cutoff = df['timestamp'].iloc[-1] - timedelta(days=limit_days)
            df = df[df['timestamp'] >= cutoff].reset_index(drop=True)
            print(f"✂️  Limiting backtest to last {limit_days} days ({len(df)} candles)")

        print(f"\n🔄 Running Strategy Replay with Real SMC Logic...")
        print(f"⚙️  Scanning candles for institutional setups...")
        
        lookback = 300 # Required for Hurst/Bias indicators
        
        for i in range(lookback, len(df) - 50): # Ensure some future data exists
            if i % 500 == 0:
                progress = (i / len(df)) * 100
                print(f"  Progress: {progress:.1f}%")

            df_slice = df.iloc[i-lookback:i+1]
            current_row = df.iloc[i]
            
            # Use real scanner (disable visual charts for speed)
            # synchronized=False to skip yfinance sync checks in backtest
            result = self.scanner.scan_pattern(
                self.symbol, 
                provided_df=df_slice, 
                current_time_override=current_row['timestamp'],
                visual_check=False
            )
            
            if result:
                setup, _ = result
                # Simulate trade outcome based on subsequent price action
                trade_result = self.simulate_trade(setup, df.iloc[i+1:])
                if trade_result:
                    self.trades.append(trade_result)
                    print(f"✅ {trade_result['timestamp']} | {trade_result['pattern']} | {trade_result['outcome']} | {trade_result['pnl_pct']:.2f}%")
        
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
            'total_pnl_pct': round(df_trades['pnl_pct'].sum(), 2),
            'avg_trade_pnl': round(df_trades['pnl_pct'].mean(), 2),
            'sharpe_ratio': round(sharpe_ratio, 2),
            'monthly_returns': {str(k): round(v, 2) for k, v in monthly_returns.items()}
        }
        
        return results

if __name__ == "__main__":
    # Test on last 7 days of BTC
    engine = BacktestEngine(
        symbol='BTC/USDT',
        start_date='2026-03-05',
        end_date='2026-03-12'
    )
    
    results = engine.run_backtest(limit_days=7)
    
    print("\n" + "="*60)
    print("📊 STRATEGY REPLAY RESULTS (Real Logic)")
    print("="*60)
    print(json.dumps(results, indent=2))
    print("="*60)

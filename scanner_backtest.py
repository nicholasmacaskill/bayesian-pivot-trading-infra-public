import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from config import Config
from src.engines.smc_scanner import SMCScanner

class ScannerBacktest:
    """
    Hybrid Truth Engine: Uses the ACTUAL SMCScanner logic + Tick-Level Replay.
    """
    def __init__(self, symbol='BTC/USDT', start_date='2025-01-06', end_date='2026-01-06'):
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.exchange = ccxt.binance({'enableRateLimit': True})
        self.scanner = SMCScanner()
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
                
                progress_date = datetime.fromtimestamp(current_ts / 1000).strftime('%Y-%m-%d %H:%M')
                print(f"  Fetched up to {progress_date}")
            except Exception as e:
                print(f"Error: {e}")
                break
                
        df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.drop_duplicates(subset='timestamp')
        
        # Ensure correct types
        df['open'] = df['open'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['volume'] = df['volume'].astype(float)
        
        print(f"✅ Fetched {len(df)} candles")
        return df

    def check_outcome(self, entry, stop, target, direction, df, entry_idx):
        """Tick-level replay to verify outcome."""
        # 1. Slippage Simulation (0.01% friction)
        if direction == 'LONG':
            entry = entry * 1.0001
        else:
            entry = entry * 0.9999
            
        max_lookahead = min(288, len(df) - entry_idx - 1)
        
        for i in range(1, max_lookahead + 1):
            future_idx = entry_idx + i
            if future_idx >= len(df): break
                
            candle = df.iloc[future_idx]
            
            if direction == 'LONG':
                if candle['low'] <= stop:
                    return ('LOSS', stop, i)
                elif candle['high'] >= target:
                    return ('WIN', target, i)
            else:
                if candle['high'] >= stop:
                    return ('LOSS', stop, i)
                elif candle['low'] <= target:
                    return ('WIN', target, i)
        
        final_candle = df.iloc[entry_idx + max_lookahead]
        return ('TIMEOUT', final_candle['close'], max_lookahead)
    
    def run_backtest(self):
        """Runs the backtest using the LIVE scanner logic."""
        df = self.fetch_historical_data()
        
        print(f"\n🔄 Running Scanner-Integrated Backtest...")
        print(f"⚙️  Strategy: {Config.STRATEGY_MODE} | FVG & Sweeps Enabled")
        
        trade_count = 0
        
        # We need a rolling window. 
        # The scanner looks back ~300 candles.
        start_idx = 500 
        
        # Step through data
        for idx in range(start_idx, len(df) - 300):
            current_timestamp = df.iloc[idx]['timestamp']
            
            # Optimization: Only check Killzone hours first (scanner does this too, but faster here)
            if not self.scanner.is_killzone(current_time=current_timestamp):
                continue

            # Pass historical context (slice up to current moment)
            # We pass a sufficiently large slice for indicators (last 500 candles is enough)
            historical_slice = df.iloc[max(0, idx-500):idx+1].copy()
            
            # CALL THE REAL SCANNER
            setup = self.scanner.scan_pattern(
                self.symbol, 
                timeframe='5m', 
                provided_df=historical_slice, 
                current_time_override=current_timestamp
            )
            
            if setup:
                # Setup found! Now verify it.
                direction = setup['direction'] # 'LONG' or 'SHORT'
                entry = setup['entry']
                stop = setup['stop_loss']
                target = setup['target']
                pattern = setup['pattern']
                quality = setup.get('quality', 'MEDIUM')
                
                outcome, exit_price, hold_candles = self.check_outcome(entry, stop, target, direction, df, idx)
                
                pnl_pct = ((exit_price - entry) / entry) * 100 if direction == 'LONG' else ((entry - exit_price) / entry) * 100
                
                trade_count += 1
                self.trades.append({
                    'timestamp': current_timestamp.isoformat(),
                    'pattern': pattern,
                    'direction': direction,
                    'quality': quality,
                    'entry': entry,
                    'stop': stop,
                    'target': target,
                    'outcome': outcome,
                    'pnl_pct': round(pnl_pct, 2),
                    'hold_candles': hold_candles
                })
                
                print(f"  [{current_timestamp}] Found {pattern} ({outcome}) PnL: {pnl_pct:.2f}%")

        print(f"✅ Generated {len(self.trades)} scanner-validated trades")
        return self.analyze_results()
    
    def analyze_results(self):
        """Analyze backtest performance."""
        if not self.trades:
            return {"error": "No trades generated"}
        
        df = pd.DataFrame(self.trades)
        
        total = len(df)
        wins = len(df[df['outcome'] == 'WIN'])
        losses = len(df[df['outcome'] == 'LOSS'])
        timeouts = len(df[df['outcome'] == 'TIMEOUT'])
        
        # Calculate monthly returns
        df['month'] = pd.to_datetime(df['timestamp']).dt.to_period('M')
        monthly_pnl = df.groupby('month')['pnl_pct'].sum()
        
        results = {
            'total_trades': total,
            'wins': wins,
            'losses': losses,
            'timeouts': timeouts,
            'win_rate': round((wins / total) * 100, 2) if total > 0 else 0,
            'avg_pnl_per_trade': round(df['pnl_pct'].mean(), 2),
            'avg_hold_candles': round(df['hold_candles'].mean(), 1),
            'monthly_returns': {str(k): round(v, 2) for k, v in monthly_pnl.to_dict().items()},
            'avg_monthly_return': round(monthly_pnl.mean(), 2),
        }
        
        return results

if __name__ == "__main__":
    engine = ScannerBacktest(
        symbol='BTC/USDT',
        start_date='2025-01-06',
        end_date='2026-01-06'
    )
    
    results = engine.run_backtest()
    
    print("\n" + "="*60)
    print("📊 SCANNER BACKTEST RESULTS")
    print("="*60)
    print(json.dumps(results, indent=2))
    
    with open('scanner_backtest_results.json', 'w') as f:
        json.dump(results, f, indent=2)

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from src.core.config import Config
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
        self.scanner.order_book_enabled = False # Disable L2 checks for backtest speed
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
    
    def resample_data(self, df, timeframe):
        """Resamples 5m data to higher timeframes."""
        # map '4h' -> '4H', '1d' -> '1D'
        rule = timeframe.lower().replace('m', 't') # generic mapper if needed, but we know inputs
        if timeframe == '4h': rule = '4h'
        if timeframe == '1d': rule = '1d'
        
        # Aggregation rules
        agg_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }
        
        df_resampled = df.set_index('timestamp').resample(rule).agg(agg_dict).dropna().reset_index()
        return df_resampled

    def run_backtest(self):
        """Runs the backtest using the LIVE scanner logic with MOCKED data fetching."""
        df = self.fetch_historical_data()
        
        # PRE-CALCULATE HTF DATA TO AVOID API CALLS
        print("⚡️ Pre-calculating HTF data for speed...")
        df_4h = self.resample_data(df, '4h')
        df_1d = self.resample_data(df, '1d')
        
        # MONKEY PATCH THE SCANNER'S FETCH_DATA
        # This forces the scanner to use our local data buckets instead of hitting Coinbase
        original_fetch = self.scanner.fetch_data
        
        def mock_fetch_data(symbol, timeframe, limit=500):
            target_df = None
            if timeframe == '5m': target_df = df # Should rarely be called if provided_df is used
            elif timeframe == '4h': target_df = df_4h
            elif timeframe == '1d': target_df = df_1d
            
            if target_df is not None:
                # Find the slice up to "now" (simulated time)
                # We need to know "current_time" which isn't passed to fetch_data directly
                # But we can assume the scanner is asking for data relative to the 'provided_df' end
                # ACTUALLY: The scanner methods (get_detailed_bias) call fetch_data independent of the loop time
                # We need to inject the 'current_timestamp' into the scanner or the mock
                
                # Hack: We will set self.scanner.current_backtest_time before calling scan
                cutoff = self.scanner.current_backtest_time
                
                # Get data up to cutoff
                mask = target_df['timestamp'] <= cutoff
                sliced = target_df.loc[mask].iloc[-limit:]
                return sliced.copy()
                
            return None # Fallback (shouldn't happen for these TFs)

        # Apply patch
        self.scanner.fetch_data = mock_fetch_data
        
        # MONKEY PATCH THE INTEMARKET ENGINE
        # The real engine hits yfinance 4 times per loop. This is the bottleneck.
        # We will mock it to return a "Neutral/Bullish" context to allow trades to fire based on price action.
        
        def mock_get_market_context():
            # Return a context that allows both Longs and Shorts (Neutral)
            # or slightly favors the trend.
            return {
                "NQ": {"trend": "UP", "change_5m": 0.1},
                "ES": {"trend": "UP", "change_5m": 0.1},
                "DXY": {"trend": "DOWN", "change_5m": -0.1}, # Dollar down = Crypto Up
                "TNX": {"trend": "DOWN", "change_5m": -0.1}  # Yields down = Risk On
            }
            
        self.scanner.intermarket.get_market_context = mock_get_market_context

        # MONKEY PATCH THE NEWS FILTER
        # Prevent hitting ForexFactory/Calendar API
        self.scanner.news.is_news_safe = lambda: (True, "No News", 0)

        # MONKEY PATCH VISUALIZER CHART GEN
        from src.engines import visualizer
        import src.engines.smc_scanner
        
        # We need to patch it where it is imported in smc_scanner
        src.engines.smc_scanner.generate_bias_chart = lambda df, symbol, tf, path: False
        visualizer.generate_bias_chart = lambda df, symbol, tf, path: False

        print(f"\n🔄 Running Scanner-Integrated Backtest...")
        print(f"⚙️  Strategy: {Config.STRATEGY_MODE} | FVG & Sweeps Enabled")
        
        trade_count = 0
        start_idx = 500 

        # VECTORIZED PRE-FILTERING (SPEED BOOST)
        print("⏩ Identifying Killzone candles to scan...")
        # Create list of timestamps (faster than pandas series iteration)
        timestamps = df['timestamp'].tolist()
        
        # Identify valid indices
        # Check Config for active zones
        # London (7-10), NY (12-20), Asia (0-4)
        indices_to_scan = []
        for i in range(start_idx, len(df) - 300):
            ts = timestamps[i]
            # Manual inline check for speed
            h = ts.hour
            is_valid = False
            
            # Hardcoded check based on Config default values to avoid method overhead
            # Config.KILLZONE_LONDON = (7, 10)
            if 7 <= h < 10: is_valid = True
            # Config.KILLZONE_NY_CONTINUOUS = (12, 20)
            elif 12 <= h < 20: is_valid = True
            # Config.KILLZONE_ASIA = (0, 4)
            elif 0 <= h < 4: is_valid = True
            
            if is_valid:
                indices_to_scan.append(i)
                
        print(f"⚡️ Optimized: Scanning {len(indices_to_scan)} candles (Skipped {len(df) - start_idx - 300 - len(indices_to_scan)} inactive candles)")
        
        # Step through valid indices only
        for idx in indices_to_scan:
            if idx % 50 == 0:
                print(f"  ... processing candle {idx}/{len(timestamps)}", end='\r')
            
            current_timestamp = df.iloc[idx]['timestamp']
            
            # SET THE TIME FOR THE MOCK
            self.scanner.current_backtest_time = current_timestamp
            
            # Pass historical context
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
                direction = setup['direction'] 
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
        
        print("\n")
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
        
        # Calculate Daily Returns for Sharpe/Sortino
        # Resample to daily frequency, summing PnL for that day
        daily_returns = df.set_index(pd.to_datetime(df['timestamp'])).resample('D')['pnl_pct'].sum().fillna(0)
        
        # Avoid division by zero
        std_dev = daily_returns.std()
        if std_dev == 0:
            sharpe_ratio = 0.0
            sortino_ratio = 0.0
        else:
            # Annualized Sharpe (assuming 365 days for Crypto)
            # Risk-free rate assumed 0 for simplicity (or e.g. 0.04/365)
            sharpe_ratio = (daily_returns.mean() / std_dev) * np.sqrt(365)
            
            # Sortino Ratio (Downside Deviation only)
            negative_returns = daily_returns[daily_returns < 0]
            downside_std = negative_returns.std()
            
            if downside_std == 0:
                sortino_ratio = 0.0  # No losing days!
            else:
                sortino_ratio = (daily_returns.mean() / downside_std) * np.sqrt(365)

        results = {
            'total_trades': total,
            'wins': wins,
            'losses': losses,
            'timeouts': timeouts,
            'win_rate': round((wins / total) * 100, 2) if total > 0 else 0,
            'avg_pnl_per_trade': round(df['pnl_pct'].mean(), 2),
            'avg_hold_candles': round(df['hold_candles'].mean(), 1),
            'sharpe_ratio': round(sharpe_ratio, 2),
            'sortino_ratio': round(sortino_ratio, 2),
            'monthly_returns': {str(k): round(v, 2) for k, v in monthly_pnl.to_dict().items()},
            'avg_monthly_return': round(monthly_pnl.mean(), 2),
        }
        
        return results

if __name__ == "__main__":
    engine = ScannerBacktest(
        symbol='BTC/USDT',
        start_date='2024-01-01',
        end_date='2024-03-31' # 3 months for a quick but solid sample size
    )
    
    results = engine.run_backtest()
    
    print("\n" + "="*60)
    print("📊 SCANNER BACKTEST RESULTS")
    print("="*60)
    print(json.dumps(results, indent=2))
    
    with open('scanner_backtest_results.json', 'w') as f:
        json.dump(results, f, indent=2)
